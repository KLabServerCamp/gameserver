# import json
import uuid

from enum import IntEnum
from typing import Optional

# from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from app.config import MAX_USER_COUNT

from .db import engine


# Enum


class LiveDifficulty(IntEnum):

    easy = 1
    normal = 2


# User


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    # 外部に見られてもいいもの

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        _ = conn.execute(
            text(
                """
                INSERT
                    INTO
                        `user` (`name`, `token`, `leader_card_id`)
                    VALUES
                        (:name, :token, :leader_card_id)
                """
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(f"create_user(): id={result.lastrowid} {token=}")
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    res = conn.execute(
        text(
            """
            SELECT
                `id`,
                `name`,
                `leader_card_id`
            FROM
                `user`
            WHERE
                `token` = :token
            """
        ),
        {"token": token},
    )
    try:
        row = res.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        return _update_user(conn=conn, token=token, name=name, leader_card_id=leader_card_id)


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    # TODO: エラーハンドリング
    _ = conn.execute(
        text(
            """
            UPDATE
                `user`
            SET
                `name` = :name,
                `leader_card_id` = :leader_card_id
            WHERE
                `token` = :token
            """
        ),
        {"name": name, "leader_card_id": leader_card_id, "token": token}
    )

    return None


# Room


class Room(BaseModel):
    id: int
    live_id: int
    max_user_count: int

    class Config:
        orm_mode = True


class RoomMember(BaseModel):
    room_id: int
    user_id: int
    select_difficulty: int

    class Config:
        orm_mode = True


def create_room(token: str, live_id: int, select_difficalty: LiveDifficulty) -> Optional[int]:
    with engine.begin() as conn:
        user_id = _get_user_by_token(conn, token).id
        return _create_room(conn, user_id, live_id, select_difficalty)


# TODO: 人数確認


def _create_room(conn, user_id: int, live_id: int, select_difficalty: LiveDifficulty) -> Optional[int]:

    res = conn.execute(
        text(
            """
            INSERT
                INTO
                    `room` (`live_id`, `max_user_count`)
                VALUES
                    (:live_id, :max_user_count)
            """
        ),
        {"live_id": live_id, "max_user_count": MAX_USER_COUNT}
    )

    try:
        id = res.lastrowid
    except NoResultFound:
        return None

    _ = conn.execute(
        text(
            """
            INSERT
                INTO
                    `room_member` (`room_id`, `user_id`, `select_difficulty`)
                VALUES
                    (:room_id, :user_id, :select_difficulty)
            """
        ),
        {"room_id": id, "user_id": user_id, "select_difficulty": select_difficalty}
    )
    return id


# room 一覧
def get_room_list(live_id: int) -> list[Room]:
    with engine.begin() as conn:

        stmt = \
            """
            SELECT
                `id`,
                `live_id`,
                `max_user_count`
            FROM
                `room`
            """

        if live_id != 0:
            stmt += \
                """
                WHERE
                    `live_id` = :live_id
                """

        res = conn.execute(
            text(stmt),
            {"live_id": live_id}
        )

        return [Room.from_orm(row) for row in res]


def get_room_members(room_id: int) -> list[RoomMember]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    `room_id`,
                    `user_id`,
                    `select_difficulty`
                FROM
                    `room_member`
                WHERE
                    `room_id` = :room_id
                """
            ),
            {"room_id": room_id}
        )
        return [RoomMember.from_orm(row) for row in res]
