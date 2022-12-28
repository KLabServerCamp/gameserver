from enum import Enum
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

import random as rand


class LiveDifficulty(Enum):
    normal = 1
    hard = 2


# NOTE:SafeRoomは閲覧可能なRoomの構成要素
class SafeRoom(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int
    
    class Config:
        orm_mode = True


def create_room(live_id: int, difficulty: int, token: str):
    with engine.begin() as conn:
        # NOTE: 必要情報の設定。
        room_id = rand.getrandbits(10)
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        try:
            row = result.one()
        except NoResultFound:
            row = [0]
        player_id = row[0]
        _ = conn.execute(
            text("INSERT INTO `room` (`live_id`,`select_difficulty`,`room_id`) VALUES (:live_id, :select_difficulty, :room_id)"),
            {"live_id": live_id, "select_difficulty": difficulty.value, "room_id": room_id},
        )
        result = conn.execute(
            text("INSERT INTO `room_member` (`room_id`, `player_id`) VALUE(:room_id, :player_id)"),
            {"room_id": room_id, "player_id": player_id},
        )
        print(result)
        return room_id


def room_list(live_id: int):
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text("SELECT `room_id`,`live_id`,`joined_user_count`,`max_user_count` FROM `room`"),
                {"live_id": live_id},
            )
        else:
            result = conn.execute(
                text("SELECT `room_id`,`live_id`,`joined_user_count`,`max_user_count` FROM `room` WHERE `live_id`=:live_id"),
                {"live_id": live_id},
            )
        rows = result.fetchall()
        rooms = [SafeRoom.from_orm(rows[n]) for n in range(len(rows))]
        return rooms

