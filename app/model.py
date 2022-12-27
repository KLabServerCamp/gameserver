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
    live_id: Optional[int]
    joined_user_count: Optional[int]
    max_user_count: Optional[int]


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: List[int]
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


def _join_room(
    conn, user_id: int, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    result = conn.execute(
        text(
            "INSERT INTO `room_member` (user_id, room_id, select_difficulty) VALUES (:user_id, :room_id, :select_difficulty)"
        ),
        {
            "user_id": user_id,
            "room_id": room_id,
            "select_difficulty": select_difficulty.value,
        },
    )
    return JoinRoomResult(1)


def join_room(
    user_id: int, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    with engine.begin() as conn:
        return _join_room(conn, user_id, room_id, select_difficulty)


def create_room(user_id: int, live_id: int, select_difficulty: LiveDifficulty) -> int:
    with engine.begin() as conn:

        result = conn.execute(
            text("INSERT INTO `room` (owner_id, live_id) VALUES (:owner_id, :live_id)"),
            {"owner_id": user_id, "live_id": live_id},
        )
        room_id = result.lastrowid

        _join_room(conn, user_id, room_id, select_difficulty)

    return room_id
