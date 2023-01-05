import json
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from app.config import MAX_USER_COUNT

from app.db import engine


from enum import IntEnum

from .user import _get_user_by_token


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
                    FOR UPDATE
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
                            (:room_id, :user_id, :select_difficulty, :is_host);
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
