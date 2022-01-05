import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine
from .room_model import LiveDifficulty, JoinRoomResult, WaitRoomStatus, RoomInfo, RoomUser, ResultUser
from .api import RoomWaitResponse
from .model import SafeUser

def _room_create(conn, live_id: int, select_difficulty: str, owner_token: str) -> int:
    result = conn.execute(
      text("INSERT INTO `room` (live_id, select_difficulty, owner_token) VALUES (:live_id, :select_difficulty, :owner_token)"),
      {"live_id": live_id, "select_difficulty": select_difficulty, "owner_token": owner_token},
    )
    return {"room_id": result.lastrowid}


def room_create(live_id: int, select_difficulty: LiveDifficulty, token: str) -> int:
    with engine.begin() as conn:
        return _room_create(conn, live_id, select_difficulty.name, token)


def _room_list_get(conn, live_id: int) -> list[RoomInfo]:
    room_info = []
    result = conn.execute(
      text("SELECT `id` AS room_id, `live_id`, `joined_user_account`, `max_user_count` FROM `room` WHERE `live_id`= :live_id"),
      {"live_id": live_id},
    )
    try:
        for row in result:
            room_info.append(RoomInfo.from_orm(row))
    except NoResultFound:
        return None
    return {"room_info_list": room_info}


def room_list_get(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        return _room_list_get(conn, live_id)


def _room_join(conn, room_id: int, select_difficulty: LiveDifficulty, user: SafeUser):
    result = conn.execute(
        text("INSERT INFO join (difficulty, user_id, room_id, is_me) VALUES (:select_dificulty, :user_id, :room_id, false)"),
        {"select_difficulty": select_difficulty.name, "user_id": user.id, "room_id": room_id},
    )
    return {"join_room_result": 0}


def room_join(room_id: int, select_difficulty: LiveDifficulty, user: SafeUser) -> JoinRoomResult:
    with engine.begin() as conn:
        return _room_join(conn, room_id, select_difficulty, user)


