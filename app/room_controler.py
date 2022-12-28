
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


def create_room(live_id: int, difficulty: int, token: str):
    with engine.begin() as conn:
        # NOTE: 必要情報の設定。
        room_id = rand.getrandbits(10)
        result = conn.execute(
            text(
                "SELECT `id` FROM `user` WHERE `token`=:token"
            ),
            {"token": token},
        )
        try:
            row = result.one()
        except NoResultFound:
            row = [0]
        player_id = row[0]
        _ = conn.execute(
            text(
                "INSERT INTO `room` (`live_id`,`select_difficulty`,`room_id`) VALUES (:live_id, :select_difficulty, :room_id)"
            ),
            {
                "live_id": live_id,
                "select_difficulty": difficulty.value,
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

