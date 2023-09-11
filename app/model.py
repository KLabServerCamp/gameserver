import json
import uuid
from enum import IntEnum

from pydantic import BaseModel  # , ConfigDict makeformatのエラー対策
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

# from .api import RoomInfo


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
                "INSERT INTO `room` (live_id, host_user_id) VALUES (:live_id, :host_user_id)"
            ),
            {"live_id": live_id, "host_user_id": user.id},
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
            room_info = conn.execute(
                text("SELECT * FROM room WHERE room_id = :room_id FOR UPDATE"),
                {"room_id": room_id},
            ).one_or_none()

            # room_member を作成
            _create_room_member(conn, user.id, room_id, difficulty)

            if room_info.room_result != JoinRoomResult.Ok:
                return room_info.room_result

            if room_info is None:
                return JoinRoomResult.Disbanded

            # room の現在の人数を更新
            if room_info.joined_user_count + 1 == room_info.max_user_count:
                conn.execute(
                    text(
                        "UPDATE room SET room_result = 2 " "WHERE room_id = :room_id "
                    ),
                    {
                        "room_id": room_id,
                    },
                )
            conn.execute(
                text(
                    "UPDATE room SET joined_user_count= :new_joined_user_count "
                    "WHERE room_id = :room_id"
                ),
                {
                    "room_id": room_id,
                    "new_joined_user_count": room_info.joined_user_count + 1,
                },
            )
            print(difficulty)

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
        room = conn.execute(
            text("SELECT * FROM room WHERE room_id = :room_id"),
            {"room_id": room_id},
        ).one_or_none()
        join_users = conn.execute(
            text(
                "SELECT user_id, select_difficulty FROM room_member "
                "WHERE room_id = :room_id"
            ),
            {"room_id": room_id},
        )
        join_users = join_users.fetchall()
        room_user_list = []
        for join_user in join_users:
            user = conn.execute(
                text("SELECT id, name, leader_card_id FROM user WHERE id=:user_id"),
                {"user_id": join_user.user_id},
            ).one_or_none()
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
        conn.execute(
            text("UPDATE room SET wait_status= 2 WHERE room_id = :room_id"),
            {"room_id": room_id},
        )


def end_room(token: str, room_id: int, judge_count_list: list[int], score: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        judge_count_json = json.dumps(judge_count_list)
        conn.execute(
            text(
                "UPDATE room_member SET judge_count_list = :judge_count_list "
                "WHERE room_id = :room_id AND user_id = :user_id"
            ),
            {
                "user_id": user.id,
                "room_id": room_id,
                "judge_count_list": judge_count_json,
            },
        )
        conn.execute(
            text(
                "UPDATE room_member SET score = :score "
                "WHERE room_id = :room_id AND user_id = :user_id"
            ),
            {"user_id": user.id, "room_id": room_id, "score": score},
        )


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
        join_users = conn.execute(
            text(
                "SELECT user_id, judge_count_list, score  FROM room_member "
                "WHERE room_id = :room_id"
            ),
            {"room_id": room_id},
        )
        join_users = join_users.fetchall()
        for join_user in join_users:
            if join_user.score is None:
                return None

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

        room = conn.execute(
            text("SELECT * FROM room WHERE room_id = :room_id"),
            {"room_id": room_id},
        ).one_or_none()

        if room.joined_user_count <= 1:
            conn.execute(
                text("UPDATE room SET room_result= 3  WHERE room_id = :room_id"),
                {"room_id": room_id},
            )
            return None

        if room.joined_user_count == room.max_user_count:
            conn.execute(
                text("UPDATE room SET room_result= 2  WHERE room_id = :room_id"),
                {"room_id": room_id},
            )

        conn.execute(
            text(
                "UPDATE room SET joined_user_count= :joined_user_count  WHERE room_id = :room_id"
            ),
            {"room_id": room_id, "join_user_count": room.join_user_count - 1},
        )

        if room.host_user_id == user.id:
            joined_member = conn.execute(
                text("SELECT * FROM room_member " "WHERE room_id = :room_id"),
                {"room_id": room_id, "user_id": user.id},
            ).one()
            conn.execute(
                text(
                    "UPDATE room SET host_user_id = :host_user_id  WHERE room_id = :room_id"
                ),
                {"room_id": room_id, "host_user_id": joined_member.user_id},
            )
