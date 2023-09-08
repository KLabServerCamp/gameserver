import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""
    print("create_room() error")


class InvalidError(Exception):
    print("Invalid error")


# サーバーで生成するオブジェクトは strict を使う
class SafeUser(BaseModel, strict=True):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    # UUID4は天文学的な確率だけど衝突する確率があるので、気にするならリトライする必要がある。
    # サーバーでリトライしない場合は、クライアントかユーザー（手動）にリトライさせることになる。
    # ユーザーによるリトライは一般的には良くないけれども、確率が非常に低ければ許容できる場合もある。
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id)"
                " VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        print(f"create_user(): {result.lastrowid=}")  # DB側で生成されたPRIMARY KEYを参照できる
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    result = conn.execute(
        text("SELECT id, name, leader_card_id FROM `user` WHERE token=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE token=:token"
            ),
            {"name": name, "leader_card_id": leader_card_id, "token": token},
        )


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""
    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    """参加判定"""
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    """ルーム状態"""
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel, strict=True):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = 4


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, room_master, joined_user_count, status)"
                " VALUES (:live_id, :room_master, :joined_user_count, :status)"
            ),
            {"live_id": live_id, "room_master": user.id, "joined_user_count": 1, "status": 1},
        )
        room_id = result.lastrowid
        result = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, difficulty)"
                " VALUES (:room_id, :user_id, :difficulty)"
            ),
            {"room_id": room_id, "user_id": user.id, "difficulty": int(difficulty)},
        )
        print(room_id)
        return room_id


def search_room(live_id: int):
    """楽曲IDから空き部屋を探す"""
    with engine.begin() as conn:
        print(f"live_id: {live_id}")
        result = conn.execute(
            text(
                """
                SELECT `id` FROM `room` WHERE live_id=:live_id AND joined_user_count BETWEEN 1 AND 3
                """
            ),
            {"live_id": live_id},
        )
        try:
            room_list = []
            row = result.all()
            for res in row:
                room_list.append(
                    res.id
                )
            print(room_list)
        except NoResultFound:
            return None
        return room_list


def join_room(token: str, room_id: int):
    """入室処理"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        judge_join = get_upto_member_room(room_id)
        if judge_join == JoinRoomResult.Ok:
            print("try join")
            user_count = get_room_user_count(room_id)
            result = insert_room_member(room_id, user.id, user_count + 1)
            if result is None:
                return JoinRoomResult.OtherError
        return judge_join


def get_room_user_count(room_id: int):
    print("get room user count")
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT joined_user_count FROM `room` WHERE id=:room_id"
            ),
            {"room_id": room_id},
        ).one()
        res = result[0]
        print(res)
        if res is None:
            return None
        return res


def get_upto_member_room(room_id: int):
    print("get upto member room")
    with engine.begin() as conn:
        res = conn.execute(
            text(
                "SELECT joined_user_count FROM `room` WHERE id=:room_id"
            ),
            {"room_id": room_id},
        ).one()
        result = res[0]
        print(f"now joined user count: {result}")
        if result > 4:
            return JoinRoomResult.OtherError
        elif result == 4:
            return JoinRoomResult.RoomFull
        elif result >= 0:
            return JoinRoomResult.Ok
        elif result < 0:
            return JoinRoomResult.Disbanded
        return JoinRoomResult.OtherError


def insert_room_member(room_id: int, user_id: int, user_count: int):
    print("room member table join")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO `room_member` (room_id, user_id, difficulty, in_order)
                 VALUES (:room_id, :user_id, :difficulty, :in_order)
                """
            ),
            {"room_id": room_id, "user_id": user_id, "difficulty": 1, "in_order": user_count},
        )

        up_joined_count(conn, room_id)
        return 1


def up_joined_count(conn, room_id: int):
    print("up user count")
    conn.execute(
        text(
            """
            UPDATE `room` SET joined_user_count = joined_user_count + 1 WHERE id=:room_id
            """
        ),
        {"room_id": room_id},
    )


def down_joined_count(conn, room_id: int):
    print("down user count")
    conn.execute(
        text(
            "UPDATE `room` SET `joined_use_count = `joined_user_count - 1 WHERE id=:room_id"
        ),
        {"id": room_id},
    )


def get_room_status(conn, room_id: int):
    print("get room status")
    result = conn.execute(
        text(
            """
            SELECT `status` FROM `room` WHERE id=:room_id
            """
        ),
        {"room_id": room_id},
    ).one()
    if result is None:
        return None
    res = result[0]
    print(f"room status: {res}")
    return WaitRoomStatus(res)


def update_room_status(room_id: int, status: WaitRoomStatus):
    print("update room status")
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `room` SET status=:status WHERE id=:room_id"
            ),
            {"status": int(status), "room_id": room_id},
        )


class UserList(BaseModel, strict=True):
    id: int
    name: str
    leader_card_id: int
    difficulty: LiveDifficulty
    is_host: bool


class RoomMemberInfo(BaseModel, strict=True):
    room_id: int
    user_id: int
    difficulty: LiveDifficulty
    in_order: int


def room_wait(room_id: int):
    with engine.begin() as conn:
        status = get_room_status(conn, room_id)
        if status is None:
            raise InvalidError(Exception)

        host = get_room_host(conn, room_id)

        print("room_idからroom_memberの各userの情報を持ってくる")
        result = conn.execute(
            text(
                """
                """
            ),
            {"room_id": room_id},
        )

        res = result.fetchall()
        print(f"get room id from user by room id from room member {res}")
        user_info: list[RoomMemberInfo] = []
        for users in res:
            print(users.id)
            print(users.name)
            print(users.leader_card_id)
            print(users.difficulty)
            if host == users.id:
                is_host = True
                print("True")
            else:
                is_host = False
                print("False")
            user_info.append(
                RoomMemberInfo(
                    id=users.id,
                    name=users.name,
                    leader_card_id=users.leader_card_id,
                    difficulty=users.difficulty,
                    is_host=is_host,
                )
            )
        return status, user_info


def get_room_host(conn, room_id: int):
    print("get room host")
    result = conn.execute(
        text(
            """
            SELECT `room_master` FROM `room` WHERE id=:room_id
            """
        ),
        {"room_id": room_id},
    ).one_or_none()
    if result is None:
        raise InvalidError(Exception)
    res = result[0]
    print(f"room_master: {res}")
    return res
