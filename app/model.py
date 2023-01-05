# import json
import json
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


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


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


def _get_user_by_id(conn, user_id: int) -> Optional[SafeUser]:
    row = conn.execute(
        text(
            """
            SELECT
                `id`,
                `name`,
                `leader_card_id`
            FROM
                `user`
            WHERE
                `id` = :user_id
            """
        ),
        {"user_id": user_id},
    )
    try:
        res = row.one()
    except NoResultFound:
        return None

    return SafeUser.from_orm(res)


def get_user_by_id(user_id: int) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_id(conn, user_id)


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

# TODO: Nullable に Optional つける
class Room(BaseModel):
    id: int
    live_id: int
    live_status: WaitRoomStatus

    class Config:
        orm_mode = True


class RoomMember(BaseModel):
    room_id: int
    user_id: int
    select_difficulty: int
    is_host: bool
    score: Optional[int]
    judge_count_list: Optional[str]

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
                    `room` (`live_id`, `live_status`)
                VALUES
                    (:live_id, :live_status)
            """
        ),
        {"live_id": live_id, "live_status": WaitRoomStatus.Waiting.value},
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


def _get_room(conn, room_id: int) -> Optional[Room]:
    res = conn.execute(
        text(
            """
            SELECT
                `id`,
                `live_id`,
                `live_status`
            FROM
                `room`
            WHERE
                `id` = :id
            """
        ),
        {"id": room_id},
    )
    try:
        res = res.one()
        res = Room.from_orm(res)
    except NoResultFound:
        return None

    return res


def get_room_list(live_id: int) -> list[Room]:
    with engine.begin() as conn:

        stmt = """
            SELECT
                `id`,
                `live_id`,
                `live_status`
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


def get_room_members(room_id: int) -> Optional[list[RoomMember]]:
    with engine.begin() as conn:
        return _get_room_members(conn, room_id)


def _get_room_members(conn, room_id: int) -> Optional[list[RoomMember]]:
    res = conn.execute(
        text(
            """
            SELECT
                `room_id`,
                `user_id`,
                `select_difficulty`,
                `is_host`,
                `score`,
                `judge_count_list`
            FROM
                `room_member`
            WHERE
                `room_id` = :room_id
            """
        ),
        {"room_id": room_id},
    )
    try:
        res = [RoomMember.from_orm(row) for row in res]
    except NoResultFound:
        return None

    return res


def join_room(token: str, room_id: int, select_difficulty: LiveDifficulty) -> JoinRoomResult:
    # TODO : lock
    with engine.begin() as conn:
        # user_id = _get_user_by_token(conn, token).id
        user = _get_user_by_token(conn, token)
        if user is None:
            return JoinRoomResult.OtherError

        users = _get_room_members(conn, room_id)
        if users is None:
            return JoinRoomResult.OtherError

        if len(users) >= MAX_USER_COUNT:
            return JoinRoomResult.RoomFull

        res = conn.execute(
            text(
                """
                    SELECT
                        `live_status`
                    FROM
                        `room`
                    WHERE
                        `id` = :room_id
                    """
            ),
            {"room_id": room_id},
        )

        try:
            room = res.one()
        except Exception:
            return JoinRoomResult.OtherError

        live_status = room["live_status"]
        if live_status == WaitRoomStatus.Dissolution:
            return JoinRoomResult.Disbanded

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


def get_room_status(room_id: int) -> WaitRoomStatus:
    with engine.begin() as conn:
        room = _get_room(conn, room_id)
        if room is None:
            return WaitRoomStatus.Dissolution

        return room.live_status


# TODO: 戻り値を Exception にする
def start_room(room_id: int, user_id: int) -> bool:
    with engine.begin() as conn:
        room = _get_room(conn, room_id)
        if room is None:
            return False

        if room.live_status != WaitRoomStatus.Waiting:
            return False

        members = _get_room_members(conn, room_id)

        for m in members:
            if m.user_id == user_id:
                if not m.is_host:
                    return False
                break

        _ = conn.execute(
            text(
                """
                UPDATE
                    `room`
                SET
                    `live_status` = :live_status
                WHERE
                    `id` = :room_id
                """
            ),
            {"live_status": WaitRoomStatus.LiveStart.value, "room_id": room_id},
        )

        return True


# TODO: 戻り値を Exception にする
def store_result(room_id: int, user_id: int, score: int, judge_count: list[int]) -> bool:
    with engine.begin() as conn:
        room = _get_room(conn, room_id)
        if room is None:
            return False

        if room.live_status != WaitRoomStatus.LiveStart:
            return False

        members = _get_room_members(conn, room_id)
        if members is None:
            return False

        me = [m for m in members if m.user_id == user_id]
        if len(me) != 1:
            return False
        me = me[0]

        try:
            _ = conn.execute(
                text(
                    """
                    UPDATE
                        `room_member`
                    SET
                        `score` = :score,
                        `judge_count_list` = :judge_count_list
                    WHERE
                        `room_id` = :room_id AND
                        `user_id` = :user_id
                    """
                ),
                {
                    "score": score,
                    "judge_count_list": json.dumps(judge_count),
                    "room_id": room_id,
                    "user_id": user_id,
                },
            )
        except Exception:
            return False

        return True


def get_result(room_id: int) -> Optional[RoomMember]:
    with engine.begin() as conn:
        room = _get_room(conn, room_id)
        if room is None:
            return None

        if room.live_status != WaitRoomStatus.LiveStart:
            return None

        members = _get_room_members(conn, room_id)
        if members is None:
            return None

        return members


def leave_room(token: str, room_id: int) -> bool:
    with engine.begin() as conn:

        me = _get_user_by_token(conn, token)
        if me is None:
            return False

        try:
            conn.execute(
                text(
                    """
                    DELETE
                    FROM
                        `room_member`
                    WHERE
                        `room_id` = :room_id AND
                        `user_id` = :user_id
                    """
                ),
                {"room_id": room_id, "user_id": me.id},
            )
        except Exception:
            return False

        return True
