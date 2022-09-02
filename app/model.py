import json
import uuid
from enum import IntEnum
from typing import Optional

import sqlalchemy.engine.base
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class LiveDifficulty(IntEnum):
    NORMAL = 1
    HARD = 2


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
        # print(result)
    return token


def _get_user_by_token(
    conn: "sqlalchemy.engine.base.Connection", token: str
) -> Optional[SafeUser]:
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token` = :token"
        ),
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
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken()
        conn.execute(
            text(
                "UPDATE `user` SET `name` = :name, `leader_card_id` = :leader_card_id WHERE `token` = :token"
            ),
            dict(name=name, leader_card_id=leader_card_id, token=token),
        )


def create_room(token: str, live_id: int) -> int:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken()
        # NOTE:room_idは一意になるようにしたい
        res = conn.execute(text("SELECT COUNT(*) FROM `room`"))
        room_id = int(res.one()[0] + 1)
        conn.execute(
            text("INSERT INTO `room` (room_id, live_id) VALUES (:room_id, :live_id)"),
            dict(room_id=room_id, live_id=live_id),
        )

    return room_id


def insert_room_member(
    room_id: int, user_token: str, live_difficulty: LiveDifficulty, is_owner: bool
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_token, live_difficulty, is_owner)"
                "VALUES (:room_id, :user_token, :live_difficulty, :is_owner)",
            ),
            dict(
                room_id=room_id,
                user_token=user_token,
                live_difficulty=int(live_difficulty),
                is_owner=is_owner,
            ),
        )
