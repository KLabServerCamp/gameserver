import json
import uuid
from enum import Enum, IntEnum
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


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
        # print(f"create_user(): id={result.lastrowid} {token=}")
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
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
        result = conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE `token`=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )


##################
# ここからroomの実装
##################


MAX_USER_COUNT = 4


class LiveDifficulty(IntEnum):
    normal: int = 1
    hard: int = 2


class JoinRoomResult(IntEnum):
    Ok: int = 1
    RoomFull: int = 2
    Disbanded: int = 3
    OhterError: int = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomStatus(BaseModel):
    room_id: int
    status: WaitRoomStatus

    class Config:
        orm_mode = True


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = MAX_USER_COUNT

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    room_id: int
    user_id: int
    live_difficulty: int
    is_me: bool = False
    is_host: bool

    class Config:
        orm_mode = True


def create_room(
    live_id: int,
    select_difficulty: LiveDifficulty,
    token: str,
) -> int:
    """Create new room and returns their room_id"""
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, joined_user_count, status) VALUES (:live_id, :joined_user_count, :room_status)"
            ),
            {
                "live_id": live_id,
                "joined_user_count": 1,
                "room_status": WaitRoomStatus.Waiting.value,
            },
        )
    # TODO: room定義時にidを割り振る
    print(f"{result=}")
    print(f"{result.lastrowid=}")
    return result.lastrowid


# TODO: get_room_list


def _get_room_list(conn, live_id: int) -> list[RoomInfo]:
    result = conn.execute(
        text(
            "SELECT `room_id`, `live_id`, `joined_user_count` FROM `room` WHERE `live_id`=:live_id"
        ),
        {"live_id": live_id},
    )
    try:
        rows = result.all()
    except NoResultFound:
        return None
    return [RoomInfo.from_orm(row) for row in rows]


def get_room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        return _get_room_list(conn, live_id)
