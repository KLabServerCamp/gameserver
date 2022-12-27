import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

# from db import engine
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

# from model import _get_user_by_token, create_user, update_user
from . import model
from .db import engine  # データベースの管理をしている


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


def _create_room(conn, live_id: int, live_difficulty: LiveDifficulty, token: str):
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
        room_id = result.one()

        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, id, name, leader_card_id) VALUES (:room_id, :id, :name, :leader_card_id)"
            ),
            {
                "room_id": room_id[0],
                "id": user.id,
                "name": user.name,
                "leader_card_id": user.leader_card_id,
            },
        )

        try:
            return room_id
        except NoResultFound:
            return None


def create_room(live_id: int, live_difficulty: LiveDifficulty, token: str):
    with engine.begin() as conn:
        return _create_room(conn, live_id, live_difficulty, token)


# def _get_room_list(conn, live_id: int):
#     with engine.begin() as conn:
#         result = conn.execute(
#             text("SELECT `room_id` FROM `room` WHERE `live_id` = :live_id"),
#             {"live_id": live_id},
#         )
#         try:

#         except NoResultFound:
#             return None


if __name__ == "__main__":
    conn = engine.connect()
    token = model.create_user(name="honoka", leader_card_id=1)
    model.update_user(token, "honono", 50)
    res = model._get_user_by_token(conn, token)
    print(res)

    res = _create_room(
        conn,
        live_id=1,
        live_difficulty=LiveDifficulty.normal,
        token=token,
    )
    print(res)
