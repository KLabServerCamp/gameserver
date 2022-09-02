import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

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

# User
def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )

    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        dict(token=token),
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
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE token=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )


# Room
def create_room(live_id: str, select_difficulty: LiveDifficulty, user: SafeUser) -> int:
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `room` (token, live_id, joined_user_count, max_user_count, room_status) VALUES (:token, :live_id, 1, :max_user_count, 1)"
            ),
            {"token": token, "live_id": live_id, "max_user_count": 4},
        )
        result = conn.execute(
            text("SELECT `room_id` FROM `room` WHERE `token`=:token"),
            dict(token=token),
        )
        id = result.one().room_id
        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, name, leader_card_id, select_difficulty, is_me, is_host) VALUES (:room_id, :user_id, :name, :leader_card_id, :select_difficulty, :is_me, :is_host)"
            ),
            {"room_id": id, "user_id": user.id, "name": user.name, "leader_card_id": user.leader_card_id, "select_difficulty": select_difficulty, "is_me": True, "is_host": True},
        )
    return id

def list_room(live_id: str) -> list:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `live_id`=:live_id AND `room_status`=1"  
            ),
            {"live_id": live_id},
        )
        rows = result.all()
    return rows

def join_room(room_id: str, select_difficulty: LiveDifficulty, user: SafeUser) -> int:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, name, leader_card_id, select_difficulty, is_me, is_host) VALUES (:room_id, :user_id, :name, :leader_card_id, :select_difficulty, :is_me, :is_host)"
            ),
            {"room_id": room_id, "user_id": user.id, "name": user.name, "leader_card_id": user.leader_card_id, "select_difficulty": select_difficulty, "is_me": True, "is_host": False},
        )
        result = conn.execute(
            text(
                "SELECT `room_status` FROM `room` WHERE `room_id`=:room_id"  
            ),
            {"room_id": room_id},
        )

    return result.room_status