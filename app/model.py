import json
import uuid
from enum import IntEnum

from pydantic import BaseModel  # , ConfigDict makeformatのエラー対策
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

# from .api import RoomInfo


class Empty(BaseModel):
    pass


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


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
    # ユーザーによるリトライは一般的には良くないけれども、
    # 確率が非常に低ければ許容できる場合もある。
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
        text(
            "SELECT `id`, `name`, `leader_card_id` FROM `user`" "WHERE `token`=:token"
        ),
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


def _get_user_by_id(conn, user_id: int):
    user = conn.execute(
        text("SELECT id, name, leader_card_id FROM user WHERE id=:user_id"),
        {"user_id": user_id},
    ).one_or_none()
    return user


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        try:
            conn.execute(
                text(
                    "UPDATE `user` "
                    "SET name=:name, leader_card_id=:leader_card_id "
                    "WHERE token=:token"
                ),
                {"token": token, "name": name, "leader_card_id": leader_card_id},
            )
        except Exception as e:
            print(f"Error updating user: {str(e)}")
            return None
        print("User updated successfully.")


def _get_room(conn, room_id: int):
    room = conn.execute(
        text("SELECT * FROM room WHERE room_id = :room_id"),
        {"room_id": room_id},
    ).one_or_none()
    return room


def _update_room(conn, room_id: int, joined_user_count=None, wait_status=None, room_result=None):
    sql = "UPDATE room SET "
    set_clauses = []

    if joined_user_count is not None:
        set_clauses.append(f"joined_user_count = {joined_user_count}")

    if wait_status is not None:
        set_clauses.append(f"wait_status = {wait_status}")

    if room_result is not None:
        set_clauses.append(f"room_result = {room_result}")

    sql += ", ".join(set_clauses)
    sql += " WHERE room_id = :room_id"

    # クエリを実行
    conn.execute(text(sql), {"room_id": room_id})  


def _get_room_members(conn, room_id: int):
    join_users = conn.execute(
        text(
            "SELECT * FROM room_member "
            "WHERE room_id = :room_id"
        ),
        {"room_id": room_id},
    )
    join_users = join_users.fetchall()
    return join_users


def _create_room_member(conn, user_id: int, room_id: int, difficulty: int):
    conn.execute(
        text(
            "INSERT INTO `room_member` (user_id, room_id, select_difficulty)"
            " VALUES (:user_id, :room_id, :select_difficulty)"
        ),
        {
            "user_id": user_id,
            "room_id": room_id,
            "select_difficulty": difficulty,
        },
    )


def _update_room_member(conn, user_id: int, room_id: int, judge_count_list: json, score: int):
    conn.execute(
        text(
            "UPDATE room_member SET judge_count_list = :judge_count_list, score = :score "
            "WHERE room_id = :room_id AND user_id = :user_id"
        ),
        {
            "user_id": user_id,
            "room_id": room_id,
            "judge_count_list": judge_count_list,
            "score": score
        },
    )


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, host_user_id) VALUES (:live_id, :user_id)"
            ),
            {"live_id": live_id, "user_id": user.id},
        )
        room_id = result.lastrowid
        _create_room_member(conn, user.id, room_id, difficulty.value)
        print(f"create_room(): {room_id=}")
    return room_id


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


def list_room(token: str, live_id: int):
    """live_idから作成されているroomを返す"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        
        if live_id == 0:
            result = conn.execute(
                text(
                    "SELECT room_id, live_id, joined_user_count, max_user_count FROM room "
                    "WHERE room_result = 1"
                ),
            )
        else:
            result = conn.execute(
                text(
                    "SELECT room_id, live_id, joined_user_count, max_user_count FROM room "
                    "WHERE live_id = :live_id AND room_result = 1"
                ),
                {"live_id": live_id},
            )

        room_info_list = [
            RoomInfo.model_validate(row, from_attributes=True)
            for row in result.fetchall()
        ]

    return room_info_list


class JoinRoomResult(IntEnum):
    """room参加結果"""

    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


def join_room(token: str, room_id: int, difficulty: LiveDifficulty):
    """room_idから入場結果を返す"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        try:
            room = conn.execute(
                text("SELECT * FROM room WHERE room_id = :room_id FOR UPDATE"),
                {"room_id": room_id},
            ).one_or_none()

            # room_member を作成
            _create_room_member(conn, user.id, room_id, difficulty)

            if room is None:
                return JoinRoomResult.Disbanded

            if room.room_result != JoinRoomResult.Ok:
                return room.room_result

            # room の現在の人数を更新
            if room.joined_user_count + 1 == room.max_user_count:
                _update_room(conn, room_id, room_result=2)
            _update_room(conn, room_id, joined_user_count=room.joined_user_count+1)
            return JoinRoomResult.Ok

        except Exception as e:
            print(f"Error updating user: {str(e)}")
            return JoinRoomResult.OtherError


class WaitRoomStatus(IntEnum):
    """room 状況"""

    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


def wait_room(token: str, room_id: int):
    with engine.begin() as conn:
        reqest_user = _get_user_by_token(conn, token)
        if reqest_user is None:
            raise InvalidToken
        room = _get_room(conn, room_id)
        join_users = _get_room_members(conn, room_id)

        room_user_list = []
        for join_user in join_users:
            user = _get_user_by_id(conn, join_user.user_id)
            if user is None:
                continue
            room_user_list.append(
                RoomUser(
                    user_id=user.id,
                    name=user.name,
                    leader_card_id=user.leader_card_id,
                    select_difficulty=LiveDifficulty(join_user.select_difficulty),
                    is_me=(user.id == reqest_user.id),
                    is_host=(user.id == room.host_user_id),
                )
            )
    return room.wait_status, room_user_list


def start_room(token: str, room_id: int):
    with engine.begin() as conn:
        reqest_user = _get_user_by_token(conn, token)
        if reqest_user is None:
            raise InvalidToken
        _update_room(conn, room_id, wait_status=2, room_result=2)


def end_room(token: str, room_id: int, judge_count_list: list[int], score: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        judge_count_json = json.dumps(judge_count_list)
        _update_room_member(conn, user.id, room_id, judge_count_json, score)   
        _update_room(conn, room_id, wait_status= 3, room_result= 3)


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


def result_room(token: str, room_id: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        result_user_list = []
        join_users = _get_room_members(conn, room_id)
        for join_user in join_users:
            if join_user.score is None:
                return Empty()

            result_user_list.append(
                ResultUser(
                    user_id=join_user.user_id,
                    judge_count_list=json.loads(join_user.judge_count_list),
                    score=join_user.score,
                )
            )
        return result_user_list


def leave_room(token: str, room_id: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        conn.execute(
            text(
                "DELETE FROM `room_member` "
                "WHERE room_id= :room_id AND user_id= :user_id"
            ),
            {"room_id": room_id, "user_id": user.id},
        )

        room = _get_room(conn, room_id)

        if room.joined_user_count <= 1:
            _update_room(conn, room_id, room_result= 3)
            return None

        if room.joined_user_count == room.max_user_count:
            _update_room(connn, room_id, room_result= 2)

        _update_room(conn, room_id, joined_user_count=room.joined_user_count-1)

        if room.host_user_id == user.id:
            joined_member = conn.execute(
                text("SELECT * FROM room_member " "WHERE room_id = :room_id"),
                {"room_id": room_id},
            ).one()
            conn.execute(
                text(
                    "UPDATE room SET host_user_id = :host_user_id  WHERE room_id = :room_id"
                ),
                {"room_id": room_id, "host_user_id": joined_member.user_id},
            )
