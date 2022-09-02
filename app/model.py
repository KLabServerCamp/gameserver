import json
import uuid
from enum import Enum, IntEnum
from typing import Optional
from unittest import result

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

class LiveDifficulty(Enum):
    normal = 1
    hard = 2

class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4

class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) \
                    VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id` FROM `user` \
                    WHERE `token`=:token"
        ),
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
                "UPDATE `user` SET `name`=:name, \
                    `leader_card_id`=:leader_card_id \
                    WHERE `token`=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
    return None


def create_room(live_id: int, select_difficulty: int, user_id: int) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` \
                (live_id, owner, joined_user_count, max_user_count) \
                VALUES (:live_id, :owner, :joined_user_count, :max_user_count)"
            ),
            {
                "live_id": live_id,
                "owner": user_id,
                "joined_user_count": 1,
                "max_user_count": 4,
            },
        )

        room_id = result.lastrowid

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id) \
                    VALUES (:room_id, :user_id)"
            ),
            {"room_id": room_id, "user_id": user_id},
        )

    return room_id


def get_rooms_by_live_id(live_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` \
                WHERE `live_id`=:live_id AND `status`=:status"
            ),
            {"live_id": live_id, "status": 1},
        )
    try:
        row = result.fetchall()
    except NoResultFound:
        return None
    return row
