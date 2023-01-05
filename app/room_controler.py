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


class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool

    class Config:
        orm_mode = True


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
            text("INSERT INTO `room_member` (`room_id`,  `owner`, `player_id`, `select_difficulty`) VALUE(:room_id, :player_id, :player_id, :select_difficulty)"),
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


def room_join(room_id: int, difficulty: LiveDifficulty, token: str) -> JoinRoomResult:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        try:
            row = result.one()
        except NoResultFound:
            return JoinRoomResult.OtherError
        player_id = row[0]
        result = conn.execute(
            text("SELECT `joined_user_count`,`max_user_count` FROM `room` WHERE `room_id`=:room_id FOR UPDATE"),
            {"room_id": room_id}
        )
        try:
            row = result.one()
        except NoResultFound:
            _ = conn.execute(text("COMMIT"))
            return JoinRoomResult.Disbanded
        if row[0] < row[1]:
            _ = conn.execute(
                text("INSERT INTO `room_member` (`room_id`, `player_id`, `select_difficulty`) VALUE(:room_id, :player_id, :select_difficulty)"),
                {"room_id": room_id, "player_id": player_id, "select_difficulty": difficulty.value},
            )
        else:
            _ = conn.execute(text("COMMIT"))
            return JoinRoomResult.RoomFull
        # NOTE:Room内の人数を数え上げ、それで人数の更新をする。
        result = conn.execute(
            text("SELECT `owner`,`player_id` FROM `room_member` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        ) 
        rows = result.fetchall()
        _ = conn.execute(
            text("UPDATE `room` SET `joined_user_count`=:num WHERE `room_id`=:room_id"),
            {"num": len(rows), "room_id": room_id},
        )
        _ = conn.execute(text("COMMIT"))
        return JoinRoomResult.Ok


def _room_member_list(room_id: int, user_id: int):
    members = []
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `player_id`, `select_difficulty`, `owner` FROM `room_member` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        row = result.fetchall()
        for player in row:
            data = conn.execute(
                text("SELECT `name`, `leader_card_id` FROM `user` WHERE `id`=:player_id"),
                {"player_id": player[0]}
            )
            try:
                data_row = data.one()
            except NoResultFound:
                continue
            members.append(RoomUser(user_id=player[0],
                                    name=data_row[0],
                                    leader_card_id=data_row[1],
                                    select_difficulty=player[1],
                                    is_me=True if player[0] == player[2] else False,
                                    is_host=True if player[0] == user_id else False))
    return members


def room_wait(room_id: int, token: str):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        user_id = result.one()[0]
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        try:
            row = result.one()
        except NoResultFound:
            return WaitRoomStatus.Dissolution, []
        if row[0] == 1:
            return WaitRoomStatus.Waiting, _room_member_list(room_id=room_id, user_id=user_id)
        else:
            return WaitRoomStatus.LiveStart, _room_member_list(room_id=room_id, user_id=user_id)