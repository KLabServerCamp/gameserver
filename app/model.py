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


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


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
        {"name": name, "leader_card_id": leader_card_id, "token": token},
    )

    return None


# Room


class Room(BaseModel):
    id: int
    live_id: int

    class Config:
        orm_mode = True


class RoomMember(BaseModel):
    room_id: int
    user_id: int
    select_difficulty: int

    class Config:
        orm_mode = True


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty) -> Optional[int]:
    with engine.begin() as conn:
        user_id = _get_user_by_token(conn, token).id
        return _create_room(conn, user_id, live_id, select_difficulty)


# TODO: 人数確認


def _create_room(conn, user_id: int, live_id: int, select_difficulty: LiveDifficulty) -> Optional[int]:

    res = conn.execute(
        text(
            """
            INSERT
                INTO
                    `room` (`live_id`)
                VALUES
                    (:live_id)
            """
        ),
        {"live_id": live_id},
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
                    `room_member` (`room_id`, `user_id`, `select_difficulty`, `is_host`)
                VALUES
                    (:room_id, :user_id, :select_difficulty, :is_host)
            """
        ),
        {"room_id": id, "user_id": user_id, "select_difficulty": select_difficulty.value, "is_host": True},
    )
    return id


# room 一覧
def get_room_list(live_id: int) -> list[Room]:
    with engine.begin() as conn:

        stmt = """
            SELECT
                `id`,
                `live_id`
            FROM
                `room`
            """

        if live_id != 0:
            stmt += """
                WHERE
                    `live_id` = :live_id
                """

        res = conn.execute(text(stmt), {"live_id": live_id})

        return [Room.from_orm(row) for row in res]


def get_room_members(room_id: int) -> list[RoomMember]:
    with engine.begin() as conn:
        res = _get_room_members(conn, room_id)
        return [RoomMember.from_orm(row) for row in res]


def _get_room_members(conn, room_id: int) -> list[RoomMember]:
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
        {"room_id": room_id},
    )
    return res


def join_room(token: str, room_id: int, select_difficulty: LiveDifficulty) -> JoinRoomResult:
    # TODO : lock
    with engine.begin() as conn:
        # user_id = _get_user_by_token(conn, token).id
        user = _get_user_by_token(conn, token)
        if user is None:
            return JoinRoomResult.OtherError

        res = _get_room_members(conn, room_id)
        users = [RoomMember.from_orm(row) for row in res]
        if len(users) >= MAX_USER_COUNT:
            return JoinRoomResult.RoomFull

        # TODO :エラーハンドリング
        try:
            conn.execute(
                text(
                    """
                    INSERT
                        INTO
                            `room_member` (`room_id`, `user_id`, `select_difficulty`, `is_host`)
                        VALUES
                            (:room_id, :user_id, :select_difficulty, :is_host)
                    """
                ),
                {
                    "room_id": room_id,
                    "user_id": user.id,
                    "select_difficulty": select_difficulty.value,
                    "is_host": False,
                },
            )
        except Exception:
            return JoinRoomResult.OtherError

        return JoinRoomResult.Ok
