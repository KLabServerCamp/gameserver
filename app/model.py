import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

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


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
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


def create_room(user_id: int, live_id: int, select_difficulty: LiveDifficulty) -> int:
    with engine.begin() as conn:

        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, joined_user_count, max_user_count) VALUES (:live_id, :joined_user_count, :max_user_count)"
            ),
            {
                "live_id": live_id,
                "joined_user_count": 1,
                "max_user_count": MAX_USER_COUNT,
            },
        )
        room_id = result.lastrowid

        _join_room(conn, user_id, room_id, select_difficulty, is_host=True)

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

        for row in result.all():
            room_info = RoomInfo.from_orm(row)
            room_info_list.append(room_info)

            # room_id: int = row["id"]
            # live_id: int = row["live_id"]
            # joined_user_count: int = row["joined_user_count"]
            # max_user_count: int = row["max_user_count"]

            # for row in result.all():
            #     room_id: int = row["id"]
            #     res = conn.execute(
            #         text("SELECT COUNT(1) FROM `room_member` WHERE `room_id`=:room_id"),
            #         {"room_id": room_id},
            #     )
            #     joined_user_count = res.one()[0]

            # room_info = RoomInfo(
            #     room_id=room_id,
            #     live_id=live_id,
            #     joined_user_count=joined_user_count,
            #     max_user_count=max_user_count,
            # )
            # room_info_list.append(room_info)

    return room_info_list


def _join_room(
    conn,
    user_id: int,
    room_id: int,
    select_difficulty: LiveDifficulty,
    is_host: bool = False,
) -> JoinRoomResult:
    result = conn.execute(
        text(
            "INSERT INTO `room_member` (user_id, room_id, select_difficulty, is_host) VALUES (:user_id, :room_id, :select_difficulty, :is_host)"
        ),
        {
            "user_id": user_id,
            "room_id": room_id,
            "select_difficulty": select_difficulty.value,
            "is_host": is_host,
        },
    )
    return JoinRoomResult.Ok


def join_room(
    user_id: int, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    with engine.begin() as conn:
        return _join_room(conn, user_id, room_id, select_difficulty)
