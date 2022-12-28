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


def create_room(live_id: int, difficulty: LiveDifficulty, token: str):
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
            text("INSERT INTO `room` (`live_id`,`room_id`) VALUES (:live_id, :room_id)"),
            {"live_id": live_id, "room_id": room_id},
        )
        result = conn.execute(
            text("INSERT INTO `room_member` (`room_id`,  `owner`, `player_id`, `select_difficulty`) VALUE(:room_id, :room_id, :player_id, :select_difficulty)"),
            {"room_id": room_id, "player_id": player_id, "select_difficulty": difficulty.value},
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
        rooms = [SafeRoom.from_orm(r) for r in rows]
        return rooms


def room_join(room_id: int, difficulty: LiveDifficulty, token: str):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        try:
            row = result.one()
        except NoResultFound:
            return 4
        player_id = row[0]
        result = conn.execute(
            text("SELECT `joined_user_count`,`max_user_count` FROM `room` WHERE `room_id`=:room_id FOR UPDATE"),
            {"room_id": room_id}
        )
        try:
            row = result.one()
        except NoResultFound:
            _ = conn.execute(text("COMMIT"))
            return 3
        if row[0] < row[1]:
            _ = conn.execute(
                text("INSERT INTO `room_member` (`room_id`, `player_id`, `select_difficulty`) VALUE(:room_id, :player_id, :select_difficulty)"),
                {"room_id": room_id, "player_id": player_id, "select_difficulty": difficulty.value},
            )
        else:
            _ = conn.execute(text("COMMIT"))
            return 2
        # NOTE:Room内の人数を数え上げ、それで人数の更新をする。
        result = conn.execute(
            text("SELECT `owner`,`player_id` FROM `room_member` WHERE `room_id`=:room_id"),
            {"room_id":room_id},
        ) 
        rows = result.fetchall()
        _ = conn.execute(
            text("UPDATE `room` SET `joined_user_count`=:num WHERE `room_id`=:room_id"),
            {"num": len(rows), "room_id": room_id},
        )
        _ = conn.execute(text("COMMIT"))
        return 1
