import json
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound


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


class Room(BaseModel):
    id: int
    live_id: Optional[int]
    live_status: Optional[WaitRoomStatus]
    user_count: Optional[int]

    class Config:
        orm_mode = True


class RoomMember(BaseModel):
    room_id: int
    user_id: int
    select_difficulty: Optional[int]
    is_host: Optional[bool]
    score: Optional[int]
    judge_count_list: Optional[str]

    class Config:
        orm_mode = True


# Room


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty) -> Optional[int]:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return None

        return _create_room(conn, user.id, live_id, select_difficulty)


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

    id = res.lastrowid

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

    res = res.one()
    res = Room.from_orm(res)

    return res


def get_room_list(
    live_id: int = None, user_max: int = None, user_min: int = None, room_status: WaitRoomStatus = None
) -> list[Room]:
    """
    Get room list

    live_id: 0のときは、全てのlive_idのルームを取得
    userLimit: (min, max)で、min以上max以下の人数のルームを取得
    room_status: 取得するルームの状態
    """
    with engine.begin() as conn:

        stmt = """
            SELECT
                `id`,
                `live_id`,
                `live_status`,
                IFNULL(`room_member_count`.`user_count`, 0) AS `user_count`
            FROM
                `room`
            LEFT OUTER JOIN
                (
                    SELECT
                        `room_id`,
                        COUNT(*) AS `user_count`
                    FROM
                        `room_member`
                    GROUP BY
                        `room_id`
                ) AS `room_member_count`
            ON
                `room`.`id` = `room_member_count`.`room_id`
            """

        where_clauses = []

        if live_id is not None:
            where_clauses.append("`live_id` = :live_id")

        if user_max is not None:
            where_clauses.append("`user_count` <= :user_max")

        if user_min is not None:
            where_clauses.append("`user_count` >= :user_min")

        if room_status is not None:
            where_clauses.append("`live_status` = :room_status")

        if len(where_clauses) > 0:
            stmt += " WHERE " + " AND ".join(where_clauses)

        res = conn.execute(
            text(stmt),
            {"live_id": live_id, "user_max": user_max, "user_min": user_min, "room_status": room_status.value},
        )

        return [Room.from_orm(row) for row in res]


def get_room_status(room_id: int) -> Optional[WaitRoomStatus]:
    with engine.begin() as conn:
        room = _get_room(conn, room_id)
        if room is None:
            return WaitRoomStatus.Dissolution

        return room.live_status


def update_room_status(room_id: int, status: WaitRoomStatus) -> None:
    with engine.begin() as conn:
        room = _get_room(conn, room_id)
        if room is None:
            raise Exception("Room not found")

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
            {"live_status": status.value, "room_id": room_id},
        )


# RoomMember


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


def add_room_member(user_id: int, room_id: int, select_difficulty: LiveDifficulty) -> None:
    with engine.begin() as conn:
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
                "user_id": user_id,
                "select_difficulty": select_difficulty.value,
                "is_host": False,
            },
        )


def update_room_member_host(room_id: int, user_id: int, is_host: bool) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE
                    `room_member`
                SET
                    `is_host` = :is_host
                WHERE
                    `room_id` = :room_id AND
                    `user_id` = :user_id
                """
            ),
            {"room_id": room_id, "user_id": user_id, "is_host": is_host},
        )


def store_room_member_result(room_id: int, user_id: int, score: int, judge_count: list[int]) -> None:
    with engine.begin() as conn:
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


def delete_room_member(user_id: int, room_id: int) -> None:
    with engine.begin() as conn:
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
            {"room_id": room_id, "user_id": user_id},
        )
