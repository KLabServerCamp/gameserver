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
    select_difficulty: int
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
        _create_room_member(
            conn, token, result.lastrowid, select_difficulty, is_host=True
        )
    return result.lastrowid


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


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty, is_host: bool = False
) -> JoinRoomResult:
    with engine.begin() as conn:
        # get num of joined user in a room
        # and return JoinRoomResult except for Ok if exceeds
        result = conn.execute(
            text(
                "SELECT joined_user_count, status FROM `room` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            row = result.one()
            if row.joined_user_count >= MAX_USER_COUNT:
                return JoinRoomResult.RoomFull
            elif row.status == WaitRoomStatus.Dissolution.value:
                return JoinRoomResult.Disbanded
        except NoResultFound:
            return JoinRoomResult.OhterError

        # update room_member talbe
        conn.excete(
            text("SELECT * FROM `room` WHERE `room_id`=:room_id FOR UPDATE"),
            {"room_id": room_id},
        )

        _create_room_member(conn, token, room_id, select_difficulty, is_host)
        _update_room_joined_user_count(conn, room_id)

        conn.execute(text("COMMIT"))
    return JoinRoomResult.Ok


def _create_room_member(
    conn, token, room_id: int, select_difficulty: LiveDifficulty, is_host: bool
) -> None:
    user = get_user_by_token(token)
    result = conn.execute(
        text(
            """
            INSERT INTO `room_member`
            (room_id, user_id, user_name, leader_card_id, select_difficulty, is_host)
            VALUES (:room_id, :user_id, :user_name, :leader_card_id, :select_difficulty, :is_host)
            """
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
            "user_name": user.name,
            "leader_card_id": user.leader_card_id,
            "select_difficulty": select_difficulty.value,
            "is_host": is_host,
        },
    )


def _update_room_joined_user_count(conn, room_id: int) -> None:
    result = conn.execute(
        text("UPDATE `room` SET joined_user_count=1 WHERE `room_id`=:room_id"),
        {"room_id": room_id},
    )


def get_room_status(room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
    return WaitRoomStatus(result.one().status)


def get_room_users(room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT `room_id`, `user_id`, `select_difficulty`, `is_host`
                FROM `room_member` WHERE `room_id`=:room_id
                """
            ),
            {"room_id": room_id},
        )
    try:
        rows = result.all()
    except NoResultFound:
        return None
    return [RoomUser.from_orm(row) for row in rows]
