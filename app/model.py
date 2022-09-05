import json
import uuid
from enum import IntEnum
from typing import Optional

import sqlalchemy.engine.base
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class LiveDifficulty(IntEnum):
    NORMAL = 1
    HARD = 2


class JoinRoomResult(IntEnum):
    OK = 1
    ROOM_FULL = 2
    DISBANDED = 3
    OTHER_ERROR = 4


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


class RoomInfo(BaseModel):
    """ルーム情報

    Attributes
    ----------
    room_id: int
        部屋識別子
    live_id: int
       プレイ対象の楽曲識別子
    joined_user_count: int
        部屋に入っている人数
    max_user_count: int
        部屋の最大人数
    """

    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(
    conn: "sqlalchemy.engine.base.Connection", token: str
) -> Optional[SafeUser]:
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token` = :token"
        ),
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
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken()
        conn.execute(
            text(
                "UPDATE `user` SET `name` = :name, `leader_card_id` = :leader_card_id WHERE `token` = :token"
            ),
            dict(name=name, leader_card_id=leader_card_id, token=token),
        )


def create_room(token: str, live_id: int) -> int:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken()
        # NOTE:room_idは一意になるようにしたい
        res = conn.execute(text("SELECT COUNT(*) FROM `room`"))
        room_id = int(res.one()[0] + 1)
        conn.execute(
            text("INSERT INTO `room` (room_id, live_id) VALUES (:room_id, :live_id)"),
            dict(room_id=room_id, live_id=live_id),
        )

    return room_id


def insert_room_member(
    room_id: int, user_id: int, live_difficulty: LiveDifficulty, is_owner: bool
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, live_difficulty, is_owner)"
                "VALUES (:room_id, :user_id, :live_difficulty, :is_owner)",
            ),
            dict(
                room_id=room_id,
                user_id=user_id,
                live_difficulty=int(live_difficulty),
                is_owner=is_owner,
            ),
        )


def _get_room_list_all() -> list[RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_token) as joined_user_count,
                    4 as max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                GROUP BY
                    room.room_id
            """
            )
        )
    res = res.fetchall()
    if len(res) == 0:
        return []
    return [RoomInfo.from_orm(row) for row in res]


def _get_room_list_by_live_id(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_token) as joined_user_count,
                    4 as max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                WHERE
                    room.live_id = :live_id
                GROUP BY
                    room.room_id
            """
            ),
            dict(live_id=live_id),
        )

    res = res.fetchall()
    if len(res) == 0:
        return []
    return [RoomInfo.from_orm(row) for row in res]


def get_room_list(live_id: int) -> list[RoomInfo]:
    # NOTE:
    # SQLでは全部取ってきて、Pythonで絞り込むようにしてもいいかも
    if live_id == 0:
        return _get_room_list_all()
    else:
        return _get_room_list_by_live_id(live_id)


def get_room_info_by_room_id(room_id: int) -> Optional[RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_token) as joined_user_count,
                    4 as max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                WHERE
                    room.room_id = :room_id
            """
            ),
            dict(room_id=room_id),
        )
        try:
            row = res.one()
        except NoResultFound:
            return None
        return RoomInfo.from_orm(row)


def join_room(
    room_id: int, user_id: int, live_difficulty: LiveDifficulty
) -> JoinRoomResult:
    room_info = get_room_info_by_room_id(room_id)

    if room_info is None or room_info.joined_user_count == 0:
        return JoinRoomResult.DISBANDED

    if room_info.joined_user_count >= room_info.max_user_count:
        return JoinRoomResult.ROOM_FULL

    # TODO:
    # すでに他のRoomに参加していたらエラーにするか、別の部屋に移動させる

    insert_room_member(room_id, user_id, live_difficulty, False)
    return JoinRoomResult.OK
