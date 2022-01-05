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
    try:
        result = conn.execute(
            text("SELECT id, joined_user_account, max_user_count, is_dissolution FROM `room` WHERE `id`= :room_id"),
            {"room_id": room_id},
        )
        res = result.one()
        room = {"id": res[0], "joined_user_account": res[1], "max_user_count": res[2], "is_dissolution": res[3]}
        print(room)
        if(room["is_dissolution"]):
            res = {"join_room_result": 3}
        else:
            if(room["joined_user_account"] < room["max_user_count"]):
                conn.execute(
                    text("INSERT INTO `join_user` (difficulty, user_id, room_id) VALUES (:select_difficulty, :user_id, :room_id)"),
                    {"select_difficulty": select_difficulty.value, "user_id": user.id, "room_id": room_id},
                )
                res = {"join_room_result": 1}
                conn.execute(
                    text("UPDATE `room` SET joined_user_account = :joined_user_account where id = :room_id"),
                    {"joined_user_account": room["joined_user_account"] + 1, "room_id": room["id"]},
                )
            else:
                res = {"join_room_result": 2}
    except:
        return {"join_room_result": 4}
    return res


def room_join(room_id: int, select_difficulty: LiveDifficulty, user: SafeUser) -> JoinRoomResult:
    with engine.begin() as conn:
        return _room_join(conn, room_id, select_difficulty, user)


