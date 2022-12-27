import json
from enum import Enum, IntEnum
from typing import Optional

# import model
# from db import engine
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from . import model
from .db import engine  # データベースの管理をしている

max_user_count = 4


class LiveDifficulty(IntEnum):
    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Wating = 1
    LiveStart = 2
    Sissolution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


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


def _create_room(
    conn, live_id: int, live_difficulty: LiveDifficulty, token: str
) -> int:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `room` (live_id, live_difficulty, token) VALUES (:live_id, :live_difficulty, :token)"
            ),
            {
                "live_id": live_id,
                "live_difficulty": live_difficulty.value,
                "token": token,
            },
        )

        user = model._get_user_by_token(conn, token)
        result = conn.execute(
            text("SELECT `room_id` FROM `room` WHERE `token` = :token"),
            {"token": token},
        )
        try:
            row = result.one()
        except NoResultFound:
            return None

        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, id, name, leader_card_id) VALUES (:room_id, :id, :name, :leader_card_id)"
            ),
            {
                "room_id": row.room_id,
                "id": user.id,
                "name": user.name,
                "leader_card_id": user.leader_card_id,
            },
        )

        return row


def create_room(live_id: int, live_difficulty: LiveDifficulty, token: str) -> int:
    with engine.begin() as conn:
        return _create_room(conn, live_id, live_difficulty, token)


# RoomInfoの取得
def get_room_info(conn, room_id: int, live_id: int) -> RoomInfo:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `name` FROM `room_member` WHERE `room_id` = :room_id"),
            {"room_id": room_id},
        )

        return RoomInfo(
            room_id=room_id,
            live_id=live_id,
            joined_user_count=len(result.all()),
            max_user_count=max_user_count,
        )


# room_listの取得
def _get_room_list(conn, live_id: int) -> Optional[list[RoomInfo]]:
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text("SELECT `room_id` FROM `room`"),
                {},
            )
        else:
            result = conn.execute(
                text("SELECT `room_id` FROM `room` WHERE `live_id` = :live_id"),
                {"live_id": live_id},
            )
        try:
            rows = result.all()
        except NoResultFound:
            return None
        return [get_room_info(conn, row.room_id, live_id) for row in rows]


def get_room_list(live_id: int) -> Optional[list[RoomInfo]]:
    with engine.begin() as conn:
        return _get_room_list(conn, live_id)


if __name__ == "__main__":
    conn = engine.connect()
    token = model.create_user(name="honoka", leader_card_id=1)
    model.update_user(token, "honono", 50)
    res = model._get_user_by_token(conn, token)
    print(res)

    result1 = _create_room(
        conn,
        live_id=1,
        live_difficulty=LiveDifficulty.normal,
        token=token,
    )
    print(result1)

    roominfo = get_room_info(conn, 1, 1)
    print(roominfo)

    result2 = get_room_list(1)
    print(list[RoomInfo])
    print(result2)
