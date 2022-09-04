import json
import uuid
from enum import Enum, IntEnum
from itertools import count
from typing import Optional
from unittest import result

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


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) \
                    VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id` FROM `user` \
                    WHERE `token`=:token"
        ),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def _get_user_id_by_token(conn, token: str) -> int:
    user_data = _get_user_by_token(conn, token)
    return user_data.id


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        # TODO: 実装
        result = conn.execute(
            text(
                "UPDATE `user` SET `name`=:name, \
                    `leader_card_id`=:leader_card_id \
                    WHERE `token`=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
    return None


def create_room(live_id: int, select_difficulty: int, token: str) -> int:
    with engine.begin() as conn:
        user_id = _get_user_id_by_token(conn, token)
        result = conn.execute(
            text(
                "INSERT INTO `room` \
                (live_id, owner, max_user_count) \
                VALUES (:live_id, :owner, :max_user_count)"
            ),
            {
                "live_id": live_id,
                "owner": user_id,
                "max_user_count": 4,
            },
        )

        room_id = result.lastrowid

        result = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, difficulty) \
                    VALUES (:room_id, :user_id, :difficulty)"
            ),
            {"room_id": room_id, "user_id": user_id, "difficulty": select_difficulty},
        )

    return room_id


def get_rooms_by_live_id(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        sql_query = "SELECT `id` AS room_id, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `status`=:status"
        sql_param = {"status": WaitRoomStatus.Waiting.value}

        if live_id != 0:
            sql_query += " AND `live_id`=:live_id"
            sql_param["live_id"] = live_id

        result = conn.execute(
            text(sql_query),
            sql_param,
        )
        try:
            rows = []
            for row in result.fetchall():
                rows.append(RoomInfo.from_orm(row))
        except NoResultFound:
            return None
    return rows


def _join_room(conn, room_id: int, select_difficulty: int, user_id: int):
    result = conn.execute(
        text(
            "INSERT INTO `room_member` (room_id, user_id, difficulty) \
                VALUES (:room_id, :user_id, :difficulty)"
        ),
        {
            "room_id": room_id,
            "user_id": user_id,
            "difficulty": select_difficulty,
        },
    )
    result = conn.execute(
        text(
            "UPDATE `room` SET `joined_user_count`=`joined_user_count` + 1 WHERE `id`=:room_id"
        ),
        {
            "room_id": room_id,
        },
    )
    return result


def join_room(room_id: int, select_difficulty: int, token: str) -> JoinRoomResult:
    with engine.begin() as conn:
        user_id = _get_user_id_by_token(conn, token)
        result = conn.execute(
            text(
                "SELECT `status`, `joined_user_count`, `max_user_count` FROM `room` WHERE `id`=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            room = result.one()
        except NoResultFound:
            return JoinRoomResult.OtherError

        if room.status == WaitRoomStatus.Waiting.value:
            if room.joined_user_count < room.max_user_count:
                result = _join_room(conn, room_id, select_difficulty, user_id)
                return JoinRoomResult.Ok
            else:
                return JoinRoomResult.RoomFull
        elif room.status == WaitRoomStatus.Dissolution.value:
            return JoinRoomResult.Disbanded
    return JoinRoomResult.OtherError


def wait_room_status(room_id: int) -> WaitRoomStatus:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `id`=:room_id"),
            {"room_id": room_id},
        )
        try:
            row = result.one()
        except NoResultFound:
            return None
    return WaitRoomStatus(row.status)


def _wait_room_host(conn, room_id: int) -> int:
    result = conn.execute(
        text("SELECT `owner` FROM `room` WHERE `id`=:room_id"),
        {"room_id": room_id},
    )
    try:
        host_user = result.one()
    except NoResultFound:
        return None
    return host_user.owner


def _get_user_by_id(conn, user_id: int):
    result = conn.execute(
        text(
            "SELECT `name`, `token`, `leader_card_id` FROM `user` WHERE `id`=:user_id"
        ),
        {"user_id": user_id},
    )
    try:
        user_data = result.one()
    except NoResultFound:
        return None
    return user_data


def wait_room_user_list(room_id: int, token: str) -> list[RoomUser]:
    with engine.begin() as conn:
        host = _wait_room_host(conn, room_id)

        result = conn.execute(
            text(
                "SELECT `user_id`, `difficulty` FROM `room_member` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            rows = []
            for user in result.fetchall():
                user_data = _get_user_by_id(conn, user.user_id)

                is_me = False
                if user_data.token == token:
                    is_me = True

                is_host = False
                if user.user_id == host:
                    is_host = True

                rows.append(
                    RoomUser(
                        user_id=user.user_id,
                        name=user_data.name,
                        leader_card_id=user_data.leader_card_id,
                        select_difficulty=user.difficulty,
                        is_me=is_me,
                        is_host=is_host,
                    )
                )
        except NoResultFound:
            return None
    return rows


def start_room(room_id: int) -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE `room` SET `status`=:status WHERE `id`=:room_id"),
            {"room_id": room_id, "status": WaitRoomStatus.LiveStart.value},
        )
    return None


def end_room(room_id: int, judge_count_list: list[int], score: int, token: str) -> None:
    with engine.begin() as conn:
        user_id = _get_user_id_by_token(conn, token)
        result = conn.execute(
            text(
                "INSERT INTO `room_result` (room_id, user_id, perfect, great, good, bad, miss) VALUES \
                (:room_id, :user_id, :perfect, :great, :good, :bad, :miss)"
            ),
            {
                "room_id": room_id,
                "user_id": user_id,
                "perfect": judge_count_list[0],
                "great": judge_count_list[1],
                "good": judge_count_list[2],
                "bad": judge_count_list[3],
                "miss": judge_count_list[4],
            },
        )
        result = conn.execute(
            text(
                "UPDATE `room_member` SET `score`=:score WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {"room_id": room_id, "user_id": user_id, "score": score},
        )
    return None


def _get_joined_user_count(conn, room_id: int) -> int:
    result = conn.execute(
        text("SELECT `joined_user_count` FROM `room` WHERE `id`=:room_id"),
        {"room_id": room_id},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return row.joined_user_count


def result_room(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        joined_user_count = _get_joined_user_count(conn, room_id)
        result = conn.execute(
            text(
                "SELECT `room_member`.`user_id`, `perfect`, `great`, `good`, `bad`, `miss`, `score` \
                    FROM `room_result` INNER JOIN `room_member` ON `room_result`.`room_id` = `room_member`.`room_id` \
                        WHERE `room_result`.`room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            rows = []
            users = result.fetchall()

            if len(users) == joined_user_count:
                for user in users:
                    rows.append(
                        ResultUser(
                            user_id=user.user_id,
                            judge_count_list=[
                                user.perfect,
                                user.great,
                                user.good,
                                user.bad,
                                user.miss,
                            ],
                            score=user.score,
                        )
                    )
        except NoResultFound:
            return None
    return rows


def _delete_room_member(conn, room_id: int, user_id: int):
    result = conn.execute(
        text(
            "DELETE FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
        ),
        {"room_id": room_id, "user_id": user_id},
    )
    return result


def _leave_room_user(conn, room_id: int, user_id: int):
    result = conn.execute(
        text(
            "UPDATE `room` SET `joined_user_count`=`joined_user_count` - 1 WHERE `id`=:room_id"
        ),
        {"room_id": room_id},
    )
    return result


def _leave_room_host(conn, room_id: int, user_id: int):
    result = conn.execute(
        text(
            "UPDATE `room` SET `status`=:status, `joined_user_count`=`joined_user_count` - 1 WHERE `id`=:room_id"
        ),
        {"room_id": room_id, "status": WaitRoomStatus.Dissolution.value},
    )
    return result


def leave_room(room_id: int, token: str) -> None:
    with engine.begin() as conn:
        user_id = _get_user_id_by_token(conn, token)
        result = _delete_room_member(conn, room_id, user_id)
        status = wait_room_status(room_id)
        host = _wait_room_host(conn, room_id)

        if host == user_id and status == WaitRoomStatus.Waiting:
            result = _leave_room_host(conn, room_id, user_id)
        else:
            result = _leave_room_user(conn, room_id, user_id)

    return None
