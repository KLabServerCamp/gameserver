
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

import random as rand

# NOTE:SafeRoomは閲覧可能なRoomの構成要素
class SafeRoom(BaseModel):
    room_id: int
    live_id: int
    difficulty: int
    player: list[str] = []


def create_room(live_id: int, difficulty: int, player_id: int):
    with engine.begin() as conn:
        room_id = rand.getrandbits(10)
        _ = conn.execute(
            text(
                "INSERT INTO `room` (`live_id`,`select_difficulty`,`room_id`) VALUES (:live_id, :select_difficulty, :room_id)"
            ),
            {
                "live_id": live_id,
                "select_difficulty": difficulty,
                "room_id": room_id
            },
        )
        result = conn.execute(
            text(
                "INSERT INTO `room_member` (`room_id`, `player_id`) VALUE(:room_id, :player_id)"
            ),
            {
                "room_id": room_id,
                "player_id": player_id
            },
        )
        print(result)
        return room_id

