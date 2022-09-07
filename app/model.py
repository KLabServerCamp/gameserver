import json
import uuid
from typing import Optional

import sqlalchemy.engine.base
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from . import schemas
from .db import engine
from .exceptions import InvalidToken, RoomNotFound

MAX_USER_COUNT = 4


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        _ = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(
    conn: "sqlalchemy.engine.base.Connection", token: str
) -> Optional[schemas.SafeUser]:
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
    return schemas.SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[schemas.SafeUser]:
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


def create_room(user_id: int, req: schemas.RoomCreateRequest) -> int:
    with engine.begin() as conn:
        res = conn.execute(text("SELECT COUNT(*) FROM `room`"))
        room_id = int(res.one()[0] + 1)
        conn.execute(
            text(
                """
                INSERT INTO `room` (
                    room_id,
                    live_id,
                    status,
                    max_user_count
                ) VALUES (
                    :room_id,
                    :live_id,
                    :status,
                    :max_user_count
                )"""
            ),
            dict(
                room_id=room_id,
                live_id=req.live_id,
                status=int(schemas.WaitRoomStatus.WAITING),
                max_user_count=MAX_USER_COUNT,
            ),
        )

        insert_room_member(conn, room_id, user_id, req.select_difficulty, True)

    return room_id


def insert_room_member(
    conn: "sqlalchemy.engine.base.Connection",
    room_id: int,
    user_id: int,
    live_difficulty: schemas.LiveDifficulty,
    is_owner: bool,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO `room_member` (
                room_id,
                user_id,
                live_difficulty,
                is_owner, is_end,
                score,
                judge
            ) VALUES (
                :room_id,
                :user_id,
                :live_difficulty,
                :is_owner,
                false,
                0,
                '')
            """,
        ),
        dict(
            room_id=room_id,
            user_id=user_id,
            live_difficulty=int(live_difficulty),
            is_owner=is_owner,
        ),
    )


def _get_room_list_all() -> list[schemas.RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_id) as joined_user_count,
                    max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                WHERE
                    room.status = :status
                GROUP BY
                    room.room_id
                HAVING
                    joined_user_count < max_user_count
            """
            ),
            dict(status=int(schemas.WaitRoomStatus.WAITING)),
        )
    res = res.fetchall()
    if len(res) == 0:
        return []
    return [schemas.RoomInfo.from_orm(row) for row in res]


def _get_room_list_by_live_id(live_id: int) -> list[schemas.RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_id) as joined_user_count,
                    max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                WHERE
                    room.live_id = :live_id
                    AND room.status = :status
                GROUP BY
                    room.room_id
                HAVING
                    joined_user_count < max_user_count
            """
            ),
            dict(live_id=live_id, status=int(schemas.WaitRoomStatus.WAITING)),
        )

    res = res.fetchall()
    if len(res) == 0:
        return []
    return [schemas.RoomInfo.from_orm(row) for row in res]


def get_room_list(live_id: int) -> list[schemas.RoomInfo]:
    # NOTE:
    # SQLでは全部取ってきて、Pythonで絞り込むようにしてもいいかも
    if live_id == 0:
        return _get_room_list_all()
    else:
        return _get_room_list_by_live_id(live_id)


def get_room_info_by_room_id(room_id: int) -> Optional[schemas.RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_id) as joined_user_count,
                    max_user_count
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
        return schemas.RoomInfo.from_orm(row)


def join_room(
    room_id: int, user_id: int, live_difficulty: schemas.LiveDifficulty
) -> schemas.JoinRoomResult:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    count(room_member.user_id) as joined_user_count,
                    max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                WHERE
                    room.room_id = :room_id
                FOR UPDATE
                """
            ),
            dict(room_id=room_id),
        )

        try:
            room_info = res.one()
        except NoResultFound:
            raise RoomNotFound()

        if room_info.joined_user_count == 0:
            return schemas.JoinRoomResult.DISBANDED

        if room_info.joined_user_count >= room_info.max_user_count:
            return schemas.JoinRoomResult.ROOM_FULL

        # TODO:
        # すでに他のRoomに参加していたらエラーにするか、別の部屋に移動させる

        insert_room_member(conn, room_id, user_id, live_difficulty, False)
        return schemas.JoinRoomResult.OK


def get_room_user_list(room_id: int, user_id: int) -> list[schemas.RoomUser]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room_member.user_id,
                    user.name,
                    user.leader_card_id,
                    room_member.live_difficulty AS select_difficulty,
                    user.id = :user_id AS is_me,
                    room_member.is_owner AS is_host
                FROM
                    room_member
                    JOIN user
                        ON room_member.user_id = user.id
                WHERE
                    room_id = :room_id
                """
            ),
            dict(room_id=room_id, user_id=user_id),
        )
    res = res.fetchall()

    if len(res) == 0:
        return []
    return [schemas.RoomUser.from_orm(row) for row in res]


def get_room_status(room_id: int) -> schemas.WaitRoomStatus:
    with engine.begin() as conn:
        res = conn.execute(
            text("SELECT status FROM room WHERE room_id = :room_id"),
            dict(room_id=room_id),
        )

    try:
        status = res.one()
    except NoResultFound:
        raise Exception("room not found")

    return schemas.WaitRoomStatus(status[0])


def start_room(room_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE room SET status = :status WHERE room_id = :room_id"),
            dict(room_id=room_id, status=int(schemas.WaitRoomStatus.LIVE_START)),
        )


def store_score(
    room_id: int, user_id: int, judge_count_list: list[int], score: int
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE room_member
                SET
                    is_end = true,
                    score = :score,
                    judge = :judge_count_list
                WHERE
                    room_id = :room_id
                    AND user_id = :user_id
            """
            ),
            dict(
                room_id=room_id,
                user_id=user_id,
                score=score,
                judge_count_list=json.dumps(judge_count_list),
            ),
        )


def get_room_result(room_id: int) -> list[schemas.ResultUser]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    user_id,
                    judge AS judge_count_list,
                    score
                FROM
                    room_member
                WHERE
                    room_id = :room_id
                    AND is_end = true
                """
            ),
            dict(room_id=room_id),
        )
    res = res.fetchall()

    if len(res) == 0:
        return []

    return [
        schemas.ResultUser(
            user_id=row.user_id,
            judge_count_list=json.loads(row.judge_count_list),
            score=row.score,
        )
        for row in res
    ]


def leave_room(room_id: int, user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM room_member WHERE room_id = :room_id AND user_id = :user_id"
            ),
            dict(room_id=room_id, user_id=user_id),
        )


def move_owner_to(room_id: int, user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE
                    room_member
                SET
                    is_owner = true
                WHERE room_id = :room_id AND user_id = :user_id
            """
            ),
            dict(room_id=room_id, user_id=user_id),
        )


def delete_room(room_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM room WHERE room_id = :room_id"),
            dict(room_id=room_id),
        )
        conn.execute(
            text("DELETE FROM room_member WHERE room_id = :room_id"),
            dict(room_id=room_id),
        )
