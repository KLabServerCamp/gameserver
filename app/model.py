import json
import uuid
from enum import Enum, IntEnum
from typing import Literal, Optional, Tuple, Union

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

MAX_USER_COUNT = 4


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class JoinRoomResult(Enum):
    Ok = 1  # 入場OK
    RoomFull = 2  # 満員
    Disbanded = 3  # 解散済み
    OtherError = 4  # その他エラー


class LiveDifficulty(Enum):
    normal = 1
    hard = 2


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO user (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        print(f"create_user(): id={result.lastrowid}")
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE token=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        # TODO: 実装
        # if get_user_by_token(token) is None:
        #     return None
        result = conn.execute(
            text(
                "UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id WHERE token=:token"
            ),
            {"token": token, "name": name, "leader_card_id": leader_card_id},
        )
        print(f"result.lastrowid={result.lastrowid}")
    return None


# CREATE TABLE `room_member` (
#   `user_id` bigint NOT NULL,
#   `room_id` bigint NOT NULL,
#   `select_difficulty` int NOT NULL,
#   `role` ENUM('host', 'guest') NOT NULL,
#   `score` int,
#   `judge_count_list` varchar(255),
#   PRIMARY KEY (`room_id`, `user_id`)
# );


class WaitRoomStatus(Enum):
    Waiting = 1  # ホストがライブ開始ボタン押すのを待っている
    LiveStart = 2  # ライブ画面遷移OK
    Dissolution = 3  # 解放された


def create_room(user_id: int, live_id: int, select_difficulty: LiveDifficulty) -> int:
    with engine.begin() as conn:

        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, joined_user_count, max_user_count, wait_room_status, host_user_id) VALUES (:live_id, :joined_user_count, :max_user_count, :wait_room_status, :host_user_id)"
            ),
            {
                "live_id": live_id,
                "joined_user_count": 1,
                "max_user_count": MAX_USER_COUNT,
                "wait_room_status": WaitRoomStatus.Waiting.value,
                "host_user_id": user_id,
            },
        )
        room_id = result.lastrowid

        _join_room(conn, user_id, room_id, select_difficulty, role="host")

    return room_id


def list_room(live_id: int):
    room_info_list: list[RoomInfo] = []
    with engine.begin() as conn:
        if live_id == 0:  # ワイルドカード
            result = conn.execute(text("SELECT *, id AS room_id FROM `room`"))
        else:
            result = conn.execute(
                text("SELECT *, id AS room_id FROM `room` WHERE `live_id`=:live_id"),
                {"live_id": live_id},
            )

        try:
            rows = result.all()
        except NoResultFound:
            return []

        for row in rows:
            room_info = RoomInfo.from_orm(row)
            room_info_list.append(room_info)
        return room_info_list


def wait_room(user_id: int, room_id: int):
    with engine.begin() as conn:
        # result = conn.execute(
        #     text("SELECT `wait_room_status` FROM `room` WHERE `id`=:room_id"),
        #     {"room_id", room_id},
        # )
        result = conn.execute(
            text("SELECT `wait_room_status` FROM `room` WHERE `id`=:room_id"),
            {"room_id": room_id},
        )

        try:
            wait_room_status: WaitRoomStatus = result.one()["wait_room_status"]
        except NoResultFound:
            return None

        result = conn.execute(
            text(
                "SELECT rm.user_id AS user_id, u.name AS name, u.leader_card_id AS leader_card_id, rm.select_difficulty AS select_difficulty, CASE WHEN rm.user_id=:user_id THEN 1 ELSE 0 END AS is_me, CASE WHEN rm.role='host' THEN 1 ELSE 0 END AS is_host FROM room_member AS rm JOIN user AS u ON rm.user_id=u.id WHERE rm.room_id=:room_id"
            ),
            {"room_id": room_id, "user_id": user_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return None

        room_user_list: list[RoomUser] = []
        for row in rows:
            room_user = RoomUser.from_orm(row)
            room_user_list.append(room_user)

    return wait_room_status, room_user_list


def get_host_user_id(room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `host_user_id` FROM `room` WHERE `id`=:room_id"),
            {"room_id": room_id},
        )
        try:
            host_user_id = result.one()["host_user_id"]
        except NoResultFound:
            return None
    return host_user_id


def start_room(user_id: int, room_id: int) -> None:
    if user_id != get_host_user_id(room_id):
        return None
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room` SET `wait_room_status`=:wait_room_status WHERE `id`=:room_id",
            ),
            {"wait_room_status": WaitRoomStatus.LiveStart.value, "room_id": room_id},
        )
    return None


def end_room(user_id: int, room_id: int, judge_count_list: list[int], score: int):
    with engine.begin() as conn:
        judge_count_list_json = json.dumps(judge_count_list)
        result = conn.execute(
            text(
                "UPDATE `room_member` SET `score`=:score, `judge_count_list`=:judge_count_list_json WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {
                "score": score,
                "judge_count_list_json": judge_count_list_json,
                "room_id": room_id,
                "user_id": user_id,
            },
        )
    return None


def result_room(room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `judge_count_list`, `score` FROM `room_member` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return []
        result_user_list = []
        for row in rows:
            row_dict = dict(row)
            row_dict["judge_count_list"] = json.loads(row_dict["judge_count_list"])
            result_user = ResultUser(**row_dict)
            result_user_list.append(result_user)
    return result_user_list


def _join_room(
    conn,
    user_id: int,
    room_id: int,
    select_difficulty: LiveDifficulty,
    role: Union[Literal["host"], Literal["guest"]],
) -> JoinRoomResult:
    result = conn.execute(
        text("SELECT COUNT(user_id) FROM `room_member` WHERE room_id=:room_id FOR UPDATE")
        , {"room_id": room_id}
        )
    if result.one()[0] >= MAX_USER_COUNT:
        conn.execute(
            text("ROLLBACK")
        )
        return JoinRoomResult.RoomFull
    result = conn.execute(
        text(
            "INSERT INTO `room_member` (user_id, room_id, select_difficulty, role) VALUES (:user_id, :room_id, :select_difficulty, :role COMMIT)"
        ),
        {
            "user_id": user_id,
            "room_id": room_id,
            "select_difficulty": select_difficulty.value,
            "role": role,
        },
    )
    return JoinRoomResult.Ok


def join_room(
    user_id: int, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    with engine.begin() as conn:
        return _join_room(conn, user_id, room_id, select_difficulty, role="guest")


def leave_room(user_id: int, room_id: int) -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "DELETE FROM `room_member` WHERE `user_id`=:user_id AND `room_id`=:room_id"
            ),
            {"user_id": user_id, "room_id": room_id},
        )


    return None
