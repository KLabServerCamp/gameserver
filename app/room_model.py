import json
from enum import Enum, IntEnum
from typing import Optional, Tuple

from fastapi import HTTPException

# from model import SafeUser
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .model import SafeUser

max_user_count = 4


class LiveDifficulty(IntEnum):
    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Wating = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


def _create_room(
    conn, live_id: int, select_difficulty: LiveDifficulty, user: SafeUser
) -> int:

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `room` (live_id, owner_id, status) "
                "VALUES (:live_id, :owner_id, :status)"
            ),
            {
                "live_id": live_id,
                "owner_id": user.id,
                "status": WaitRoomStatus.Wating.value,
            },
        )

        result = conn.execute(
            text("SELECT `room_id` FROM `room` WHERE `owner_id` = :owner_id"),
            {"owner_id": user.id},
        )
        row = result.one()

        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, select_difficulty, score, judge) "
                "VALUES (:room_id, :user_id, :select_difficulty, :score, :judge)"
            ),
            {
                "room_id": row.room_id,
                "user_id": user.id,
                "select_difficulty": select_difficulty.value,
                "score": None,
                "judge": None,
            },
        )

        return row


def create_room(live_id: int, select_difficulty: LiveDifficulty, token: str) -> int:
    with engine.begin() as conn:
        user = model._get_user_by_token(conn, token)
        if user is None:
            raise HTTPException(status_code=404)

        return _create_room(conn, live_id, select_difficulty, user)


# RoomInfoの取得
def get_room_info(conn, room_id: int, live_id: int) -> RoomInfo:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `user_id` FROM `room_member` WHERE `room_id` = :room_id"),
            {"room_id": room_id},
        )

        return RoomInfo(
            room_id=room_id,
            live_id=live_id,
            joined_user_count=len(result.all()),
            max_user_count=max_user_count,
        )


# room_listの取得
def _get_room_list(conn, live_id: int) -> Optional[list[RoomInfo]]:
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text("SELECT `room_id`, `live_id` FROM `room`"),
                {},
            )
        else:
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id` FROM `room` WHERE `live_id` = :live_id"
                ),
                {"live_id": live_id},
            )
        try:
            rows = result.all()
        except NoResultFound:
            return None
        return [get_room_info(conn, row.room_id, row.live_id) for row in rows]


def get_room_list(live_id: int) -> Optional[list[RoomInfo]]:
    with engine.begin() as conn:
        return _get_room_list(conn, live_id)


# ルームの状態を確認
def room_status_check(conn, room_id: int) -> Optional[WaitRoomStatus]:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id` = :room_id FOR UPDATE"),
            {"room_id": room_id},
        )

        try:
            room_status = result.one().status
        except NoResultFound:
            return WaitRoomStatus.Dissolution

        return room_status


# ルームに入場する
def _room_join(
    conn, room_id: int, select_difficulty: LiveDifficulty, user_id: int
) -> Optional[JoinRoomResult]:

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id` FROM `room_member` WHERE `room_id` = :room_id FOR UPDATE"
            ),
            {"room_id": room_id},
        )

        if len(result.all()) > max_user_count - 1:
            return JoinRoomResult.RoomFull

        result = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, select_difficulty, score, judge) "
                "VALUES (:room_id, :user_id, :select_difficulty, :score, :judge)"
            ),
            {
                "room_id": room_id,
                "user_id": user_id,
                "select_difficulty": select_difficulty.value,
                "score": None,
                "judge": None,
            },
        )

        try:
            res = result
        except NoResultFound:
            return JoinRoomResult.OtherError
        return JoinRoomResult.Ok


def room_join(
    room_id: int, select_difficulty: LiveDifficulty, token: str
) -> Optional[JoinRoomResult]:

    with engine.begin() as conn:
        if room_status_check(conn, room_id) == WaitRoomStatus.Dissolution:
            return JoinRoomResult.Disbanded

        user = model._get_user_by_token(conn, token)
        if user is None:
            return JoinRoomResult.OtherError

        return _room_join(conn, room_id, select_difficulty, user.id)


# ルーム内のユーザの確認
def user_check(
    conn,
    room_id: int,
    req_user_id: int,
    user_id: int,
    select_difficulty: LiveDifficulty,
) -> Optional[RoomUser]:
    with engine.begin() as conn:
        is_host = False
        is_me = False

        result = conn.execute(
            text("SELECT `owner_id` FROM `room` WHERE `room_id` = :room_id"),
            {"room_id": room_id},
        )
        row = result.one()
        if user_id == row.owner_id:
            is_host = True

        result = conn.execute(
            text("SELECT `name`, `leader_card_id` FROM `user` WHERE `id` = :user_id"),
            {"user_id": user_id},
        )
        row = result.one()
        if req_user_id == user_id:
            is_me = True

        return RoomUser(
            user_id=user_id,
            name=row.name,
            leader_card_id=row.leader_card_id,
            select_difficulty=select_difficulty,
            is_me=is_me,
            is_host=is_host,
        )


# ルーム待機
def _room_wait(
    conn, room_id: int, user: SafeUser
) -> Tuple[WaitRoomStatus, list[RoomUser]]:

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `select_difficulty` FROM `room_member` WHERE `room_id` = :room_id FOR UPDATE"
            ),
            {"room_id": room_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return (WaitRoomStatus.Dissolution, None)

        user_list = [
            user_check(conn, room_id, user.id, row.user_id, row.select_difficulty)
            for row in rows
        ]

        if len(rows) < max_user_count:
            return (WaitRoomStatus.Wating, user_list)

        return (WaitRoomStatus.LiveStart, user_list)


def room_wait(room_id: int, token: str) -> Tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        user = model._get_user_by_token(conn, token)
        return _room_wait(conn, room_id, user)


if __name__ == "__main__":
    import model
    from db import engine

    conn = engine.connect()
    token = model.create_user(name="honoka", leader_card_id=1)
    model.update_user(token, "honono", 50)
    res = model._get_user_by_token(conn, token)
    print("user:", res)

    result1 = _create_room(
        conn,
        live_id=1,
        select_difficulty=LiveDifficulty.normal,
        user=res,
    )
    print("room_id:", result1)

    result2 = get_room_list(1)
    print("roomlist:", result2)

    result3 = _room_join(conn, 1, LiveDifficulty.normal, res)
    print("join_result:", result3)

else:
    from . import model
    from .db import engine  # データベースの管理をしている
