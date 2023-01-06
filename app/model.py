import json
import uuid
from enum import Enum, IntEnum
from typing import Optional, cast

from fastapi import HTTPException
from pydantic import BaseModel, validator
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import NoResultFound
from sqlalchemy.future import Connection

from . import config
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
        # print(f"create_user(): id={result.lastrowid} {token=}")
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    res = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM user WHERE `token` = :token"),
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


def _update_user_by_token(conn, token: str, name: str, leader_card_id: int) -> None:
    conn.execute(
        text(
            "UPDATE `user` SET `name` = :name, `leader_card_id` = :leader_card_id WHERE `token` = :token"
        ),
        {"token": token, "name": name, "leader_card_id": leader_card_id},
    )


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        return _update_user_by_token(conn, token, name, leader_card_id)


class LiveDifficulty(IntEnum):
    NORMAL = 1
    HARD = 2


class JoinRoomResult(IntEnum):
    OK = 1
    ROOM_FULL = 2
    DISBANDED = 3
    OTHER_ERROR = 4


class WaitRoomStatus(IntEnum):
    WAITING = 1
    LIVE_START = 2
    DISSOLUTION = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = config.ROOM_MAX_USER_COUNT

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

    @validator("judge_count_list", pre=True)
    def deserialize_json_str(cls, v: str | list[int]):
        if isinstance(v, str):
            return json.loads(v)
        return v


def _create_room(conn: Connection, user_id: int, live_id: int) -> Optional[int]:
    res: CursorResult = conn.execute(
        text(
            "INSERT INTO `room` (`host_id`, `live_id`, `status`) "
            "VALUES (:host_id, :live_id, :status) "
        ),
        {
            "host_id": user_id,
            "live_id": live_id,
            "status": WaitRoomStatus.WAITING.value,
        },
    )

    return cast(int, res.lastrowid)


def _get_room_status(
    conn: Connection, room_id: int, *, for_update: bool = False
) -> Optional[WaitRoomStatus]:
    q = "SELECT * FROM room WHERE id = :id LIMIT 1"
    if for_update:
        q += " FOR UPDATE"

    res: CursorResult = conn.execute(text(q), {"id": room_id})

    try:
        row = res.one()
        return row["status"]
    except NoResultFound:
        return None


def _set_room_status(conn: Connection, room_id: int, status: WaitRoomStatus):
    _: CursorResult = conn.execute(
        text("UPDATE `room` SET `status` = :status WHERE `id` = :room_id"),
        {
            "room_id": room_id,
            "status": status.value,
        },
    )


def _count_room_member(conn: Connection, room_id: int) -> Optional[int]:
    res: CursorResult = conn.execute(
        text(
            "SELECT COUNT(*) AS joined_user_count FROM room_member "
            "WHERE room_id = :room_id "
            "LOCK IN SHARE MODE"
        ),
        {"room_id": room_id},
    )

    try:
        row = res.one()
        return row["joined_user_count"]
    except NoResultFound:
        return None


def _join_room(
    conn: Connection, user_id: int, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    match _get_room_status(conn, room_id, for_update=True):
        case WaitRoomStatus.WAITING:
            pass
        case WaitRoomStatus.LIVE_START:
            return JoinRoomResult.ROOM_FULL
        case WaitRoomStatus.DISSOLUTION:
            return JoinRoomResult.DISBANDED
        case _:
            return JoinRoomResult.OTHER_ERROR

    joined_user_count = _count_room_member(conn, room_id)
    if joined_user_count is None:
        return JoinRoomResult.OTHER_ERROR
    if joined_user_count >= config.ROOM_MAX_USER_COUNT:
        return JoinRoomResult.ROOM_FULL

    conn.execute(
        text(
            "INSERT INTO `room_member` (`user_id`, `room_id`, `select_difficulty`) "
            "VALUES (:user_id, :room_id, :select_difficulty) "
        ),
        {
            "user_id": user_id,
            "room_id": room_id,
            "select_difficulty": select_difficulty.value,
        },
    )
    return JoinRoomResult.OK


def create_room(
    token: str, live_id: int, select_difficulty: LiveDifficulty
) -> Optional[int]:
    with engine.begin() as conn:
        conn = cast(Connection, conn)
        host = _get_user_by_token(conn, token)
        if host is None:
            return None

        room_id = _create_room(conn, host.id, live_id)
        if room_id is None:
            return None

        _join_room(conn, host.id, room_id, select_difficulty)

        return room_id


def _get_room_list_all(conn: Connection) -> list[RoomInfo]:
    res: CursorResult = conn.execute(
        text(
            "SELECT `room_id`, `live_id`, COUNT(*) AS `joined_user_count` "
            "FROM room "
            "INNER JOIN room_member ON room.id = room_id "
            "WHERE `status` = :WAITING "
            "GROUP BY `room_id`, `live_id`"
        ),
        {
            "WAITING": WaitRoomStatus.WAITING.value,
        },
    )
    return [RoomInfo(**row) for row in res]


def _get_room_list_by_live_id(conn: Connection, live_id: int) -> list[RoomInfo]:
    res: CursorResult = conn.execute(
        text(
            "SELECT `room_id`, `live_id`, COUNT(*) AS `joined_user_count` "
            "FROM room "
            "INNER JOIN room_member ON room.id = room_id "
            "WHERE `live_id` = :live_id AND `status` = :WAITING "
            "GROUP BY `room_id`, `live_id`"
        ),
        {
            "live_id": live_id,
            "WAITING": WaitRoomStatus.WAITING.value,
        },
    )

    return [RoomInfo(**row) for row in res]


def get_room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        conn = cast(Connection, conn)

        if live_id == 0:
            return _get_room_list_all(conn)
        else:
            return _get_room_list_by_live_id(conn, live_id)


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty
) -> Optional[JoinRoomResult]:
    with engine.begin() as conn:
        conn = cast(Connection, conn)
        user = _get_user_by_token(conn, token)
        if user is None:
            return None

        return _join_room(conn, user.id, room_id, select_difficulty)


def _get_room_user_list(conn: Connection, request_user_id: int, room_id: int) -> list[RoomUser]:
    res: CursorResult = conn.execute(
        text(
            "SELECT "
            "`user_id`, `name`, `leader_card_id`, `select_difficulty`, "
            "`user_id` = :request_user_id AS `is_me`, `user_id` = `host_id` AS `is_host` "
            "FROM `user` "
            "INNER JOIN `room_member` ON `user`.`id` = `user_id` "
            "INNER JOIN `room` ON `room_id` = `room`.`id` "
            "WHERE `room_id` = :room_id"
        ),
        {"request_user_id": request_user_id, "room_id": room_id},
    )
    return [RoomUser(**row) for row in res]


def wait_room(
    token: str, room_id: int
) -> Optional[tuple[WaitRoomStatus, list[RoomUser]]]:
    with engine.begin() as conn:
        conn = cast(Connection, conn)
        user = _get_user_by_token(conn, token)
        if user is None:
            return None

        status = _get_room_status(conn, room_id)
        if status is None:
            return None

        room_user_list = _get_room_user_list(conn, user.id, room_id)

        return status, room_user_list


def _is_host(conn: Connection, user_id: int, room_id: int) -> bool:
    res: CursorResult = conn.execute(
        text("SELECT * FROM `room` WHERE `id` = :room_id AND `host_id` = :user_id"),
        {
            "room_id": room_id,
            "user_id": user_id,
        },
    )

    try:
        _ = res.one()
        return True
    except NoResultFound:
        return False


def _leave_room(conn: Connection, user_id: int, room_id: int):
    # disband room on host leaving
    if _is_host(conn, user_id, room_id):
        _set_room_status(conn, room_id, WaitRoomStatus.DISSOLUTION)

    _: CursorResult = conn.execute(
        text(
            "DELETE FROM `room_member` WHERE `room_id` = :room_id AND `user_id` = :user_id"
        ),
        {"user_id": user_id, "room_id": room_id},
    )


def leave_room(token: str, room_id: int):
    with engine.begin() as conn:
        conn = cast(Connection, conn)
        user = _get_user_by_token(conn, token)
        if user is None:
            return

        _leave_room(conn, user.id, room_id)


def _start_room(conn: Connection, room_id: int):
    _set_room_status(conn, room_id, WaitRoomStatus.LIVE_START)


def start_room(token: str, room_id: int):
    with engine.begin() as conn:
        conn = cast(Connection, conn)
        user = _get_user_by_token(conn, token)
        if user is None:
            return

        # host only
        if _is_host(conn, user.id, room_id):
            _start_room(conn, room_id)


def _end_room(
    conn: Connection,
    user_id: int,
    room_id: int,
    judge_count_list: list[int],
    score: int,
):
    _: CursorResult = conn.execute(
        text(
            "UPDATE `room_member` "
            "SET `judge_count_list` = :judge_count_list, `score` = :score "
            "WHERE `user_id` = :user_id AND `room_id` = :room_id"
        ),
        {
            "user_id": user_id,
            "room_id": room_id,
            "judge_count_list": json.dumps(judge_count_list),
            "score": score,
        },
    )


def end_room(token: str, room_id: int, judge_count_list: list[int], score: int):
    with engine.begin() as conn:
        conn = cast(Connection, conn)
        user = _get_user_by_token(conn, token)
        if user is None:
            return

        _end_room(conn, user.id, room_id, judge_count_list, score)


def _has_all_live_ended(conn: Connection, room_id: int) -> bool:
    res: CursorResult = conn.execute(
        text(
            "SELECT COUNT(*) AS in_game_count FROM `room_member` "
            "WHERE `room_id` = :room_id AND `score` IS NULL"
        ),
        {"room_id": room_id},
    )

    try:
        row = res.one()
        return row["in_game_count"] == 0
    except NoResultFound:
        return True


def _get_result(conn: Connection, room_id: int) -> list[ResultUser]:
    res: CursorResult = conn.execute(
        text(
            "SELECT `user_id`, `judge_count_list`, `score` "
            "FROM `room_member` "
            "WHERE `room_id` = :room_id"
        ),
        {"room_id": room_id},
    )

    return [ResultUser(**row) for row in res]


def get_result(token: str, room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        conn = cast(Connection, conn)
        user = _get_user_by_token(conn, token)
        if user is None:
            return []

        if _has_all_live_ended(conn, room_id):
            res = _get_result(conn, room_id)
            if _is_host(conn, user.id, room_id):
                _set_room_status(conn, room_id, WaitRoomStatus.DISSOLUTION)
            return res
        else:
            return []
