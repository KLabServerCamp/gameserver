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


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int

    class Config:
        orm_mode = True


# User
def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )

    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        dict(token=token),
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
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE token=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )


# Room
def create_room(live_id: int, select_difficulty: LiveDifficulty, user: SafeUser) -> int:
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `room` (token, live_id, joined_user_count, max_user_count, join_status, wait_status) VALUES (:token, :live_id, 1, :max_user_count, 1, 1)"
            ),
            {"token": token, "live_id": live_id, "max_user_count": 4},
        )
        result = conn.execute(
            text("SELECT `room_id` FROM `room` WHERE `token`=:token"),
            dict(token=token),
        )
        room_id = result.one().room_id
        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, name, leader_card_id, select_difficulty, is_me, is_host) VALUES (:room_id, :user_id, :name, :leader_card_id, :select_difficulty, :is_me, :is_host)"
            ),
            {
                "room_id": room_id,
                "user_id": user.id,
                "name": user.name,
                "leader_card_id": user.leader_card_id,
                "select_difficulty": select_difficulty.value,
                "is_me": True,
                "is_host": True,
            },
        )
    return room_id


def list_room(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `live_id`=:live_id AND `join_status`=1"
            ),
            {"live_id": live_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return None

    return [RoomInfo.from_orm(row) for row in rows]


def join_room(
    room_id: int, select_difficulty: LiveDifficulty, user: SafeUser
) -> JoinRoomResult:
    with engine.begin() as conn:
        ans = 1
        conn.execute(
            text("SELECT * FROM room WHERE `room_id`=:room_id FOR UPDATE"),
            {"room_id": room_id},
        )
        result = conn.execute(
            text("SELECT `max_user_count` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        max_user_count = result.one()[0]
        result = conn.execute(
            text("SELECT COUNT(1) FROM room_member WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        cnt = result.one()[0]

        if cnt < max_user_count:
            conn.execute(
                text(
                    "INSERT INTO `room_member` (room_id, user_id, name, leader_card_id, select_difficulty, is_me, is_host) VALUES (:room_id, :user_id, :name, :leader_card_id, :select_difficulty, :is_me, :is_host)"
                ),
                {
                    "room_id": room_id,
                    "user_id": user.id,
                    "name": user.name,
                    "leader_card_id": user.leader_card_id,
                    "select_difficulty": select_difficulty.value,
                    "is_me": True,
                    "is_host": False,
                },
            )
            if cnt == max_user_count - 1:
                conn.execute(
                    text("UPDATE `room` SET join_status=2 WHERE room_id=:room_id"),
                    {"room_id": room_id},
                )

            conn.execute(text("COMMIT"))
        else:
            conn.execute(text("ROLLBACK"))
            ans = 2

    return ans


def wait_room(room_id: int) -> dict:
    with engine.begin() as conn:
        status = 1
        result = conn.execute(
            text(
                "SELECT `user_id`, `name`, `leader_card_id`, `select_difficulty`, `is_me`, `is_host` FROM `room_member` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return None

        room_user_list = [RoomUser.from_orm(row) for row in rows]

    return {"status": status, "room_user_list": room_user_list}


def start_room(room_id: int, user: SafeUser) -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `is_host` FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {"room_id": room_id, "user_id": user.id},
        )
        try:
            row = result.one()
        except NoResultFound:
            return None
        if row.is_host != 1:
            return None
        conn.execute(
            text(
                "UPDATE `room` SET join_status=2, wait_status=2 WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )


def end_room(
    room_id: int, judge_count_list: list[int], score: int, user: SafeUser
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `room_member` SET judge1=:judge1, judge2=:judge2, judge3=:judge3, judge4=:judge4, judge5=:judge5, score=:score WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {
                "judge1": judge_count_list[0],
                "judge2": judge_count_list[1],
                "judge3": judge_count_list[2],
                "judge4": judge_count_list[3],
                "judge5": judge_count_list[4],
                "score": score,
                "room_id": room_id,
                "user_id": user.id,
            },
        )


def result_room(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `judge1`, `judge2`, `judge3`, `judge4`, `judge5`, `score` FROM `room_member` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return None
        result_user_list = []
        for row in rows:
            result_user_list.append(
                ResultUser(
                    user_id=row[0],
                    judge_count_list=[row[i] for i in range(1, 6)],
                    score=row[6],
                )
            )

    return result_user_list


def leave_room(room_id: int, user: SafeUser) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {"room_id": room_id, "user_id": user.id},
        )
