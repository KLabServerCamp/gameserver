# import json
import uuid

from enum import Enum, IntEnum
from typing import Optional

# from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from app.db import engine


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


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id)"
                + " VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        print("lastrowid: ", result.lastrowid)
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    """fetch user data"""
    # TODO: 実装
    result = conn.execute(
        text("SELECT * FROM `user` WHERE `token` = :token"),
        {"token": token},
    )
    try:
        row = result.one()
        print(row)
    except NoResultFound:
        return None
    # print(result)
    return row


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def _get_user(conn) -> Optional[SafeUser]:
    """fetch user data"""
    # TODO: 実装
    result = conn.execute(
        text("SELECT * FROM `user`"),
    )
    try:
        # rows = result.all()
        # print(rows)

        for row in result:
            print(row)

    except NoResultFound:
        return None
    # print(result)
    return None


def get_user() -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user(conn)


def _update_user_by_token(
    conn, token: str, name: str, leader_card_id: str
) -> Optional[SafeUser]:
    """update user data"""
    # TODO: 実装
    result = conn.execute(
        text(
            "UPDATE `user` SET `name`= :name,"
            + "`leader_card_id`= :leader_card_id"
            + " WHERE `token` = :token"
        ),
        {"name": name, "leader_card_id": leader_card_id, "token": token},
    )
    print(result)
    return


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # tokenベースでnameとleader_card_idを変更
    with engine.begin() as conn:
        return _update_user_by_token(conn, token, name, leader_card_id)


def _create_room(
    conn, token: str, live_id: int, select_difficulty: LiveDifficulty
) -> int:
    result = conn.execute(
        text(
            "INSERT INTO `room`"
            + " (live_id, owner_token, status, joined_user_count, max_user_count)"
            + " VALUES (:live_id, :token, :status, 1, 4)"
        ),
        {"live_id": live_id, "token": token, "status": 0},
    )
    room_id = result.lastrowid
    result2 = _get_user_by_token(conn, token)
    print(result2)
    print(result2)
    print(result2)
    print(result2)
    user_id = 0
    result3 = conn.execute(
        text(
            "INSERT INTO `room_member` (room_id, user_id, score,"
            + "judge, token, select_difficulty)"
            + " VALUES (:room_id, :user_id, :score,"
            + " :judge, :token, :select_difficulty)"
        ),
        {
            "room_id": room_id, "user_id": user_id, 
            "score": 0, "judge": 0, "token": token,
            "select_difficulty": select_difficulty.value
        },
    )
    print(result3)
    return room_id


def create_room(
    token: str, live_id: int, select_difficulty: LiveDifficulty
) -> int:
    """Create new room and returns its id"""
    with engine.begin() as conn:
        return _create_room(conn, token, live_id, select_difficulty)


def _list_room(
    conn, token: str, live_id: str
) -> dict:
    result = conn.execute(
        text(
            "SELECT id, live_id, owner_token, joined_user_count,"
            + " max_user_count FROM `room`"
            + " WHERE live_id = :live_id AND joined_user_count"
            + " < max_user_count"
        ),
        {"live_id": live_id},
    )
    output = []
    for row in result:
        output.append(
            dict(
                room_id=row.id,
                live_id=row.live_id,
                owner_token=row.owner_token,
                joined_user_count=row.joined_user_count,
                max_user_count=row.max_user_count
            )
        )
    # print(output)
    return output


def list_room(token: str, live_id: int) -> dict:
    """Create new room and returns its id"""
    with engine.begin() as conn:
        return _list_room(conn, token, live_id)
