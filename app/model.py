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


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    res = conn.execute(
        text("select id, name, leader_card_id from user where token = :token"),
        {"token": token},
    )
    try:
        row = res.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def dummy_func():
    print("Im dummy :D")


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    res = conn.execute(
        text(
            "update user set name = :name, leader_card_id = :card where token = :token"
        ),
        {"name": name, "card": leader_card_id, "token": token},
    )


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        _update_user(conn, token, name, leader_card_id)


# 以下マルチプレイ用


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
    max_user_cout: int


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


def _create_room(conn, user: SafeUser, live_id: int, live_dif: LiveDifficulty) -> int:
    users = {0: [user.id, user.leader_card_id, live_dif.value]}
    users_json = json.dumps(users)
    result = conn.execute(
        text(
            "INSERT INTO `rooms` (live_id, j_usr_cnt, m_usr_cnt, hst_id, users) \
            VALUES (:live_id, 1, 4, 0, :users)"
        ),
        {"live_id": live_id, "users": users_json},
    )
    room_id = result.lastrowid
    return room_id


def create_room(token: str, live_id: int, live_dif: LiveDifficulty) -> int:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken("指定されたtokenが不正です")
        return _create_room(conn, user, live_id, live_dif)


def _room_list(conn, live_id: int) -> list[RoomInfo]:
    execute_sent = "SELECT room_id, live_id, j_usr_cnt, m_usr_cnt FROM rooms"
    result = None
    if live_id != 0:
        result = conn.execute(text(execute_sent))
    else:
        result = conn.execute(
            text(execute_sent + " WHERE live_id = :live_id"),
            {"live_id": live_id}
        )
    rows = result.all()
    room_infos = [RoomInfo(room_id=row.room_id, live_id=row.live_id,
                           joined_user_count=row.j_usr_cnt,
                           max_user_cout=row.m_usr_cnt) for row in rows]
    return room_infos


def room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        return _room_list(conn, live_id)