import random
from typing import Optional
from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from ..config import JUDGE_COLUMNS, MAX_USER_COUNT
from ..db import engine
from . import model, user_impl


def commit(conn):
    conn.execute(text("COMMIT"))


def rollback(conn):
    conn.execute(text("ROLLBACK"))


def create_room(
    live_id: int, select_difficulty: model.LiveDifficulty, token: str
) -> int:
    with engine.begin() as conn:
        return _create_room(conn, live_id, select_difficulty, token)


def _create_room(
    conn, live_id: int, select_difficulty: model.LiveDifficulty, token: str
) -> int:
    # room_idも衝突を回避する必要がある
    room_id = random.randint(0, 1000000000)
    while not (_get_room_by_room_id(conn, room_id) is None):
        room_id = random.randint(0, 1000000000)

    _ = conn.execute(
        text(
            "INSERT INTO `room` (live_id, room_id, joined_user_count, max_user_count, status) VALUES (:live_id, :room_id, :joined_user_count, :max_user_count, :status)"
        ),
        {
            "live_id": live_id,
            "room_id": room_id,
            "joined_user_count": 1,
            "max_user_count": MAX_USER_COUNT,
            "status": model.WaitRoomStatus.Waiting.value,
        },
    )

    user = user_impl._get_user_by_token(conn, token)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    _ = conn.execute(
        text(
            "INSERT INTO `room_member` (name, room_id, user_id, token, is_host, select_difficulty) VALUES (:name, :room_id, :user_id, :token, :is_host, :select_difficulty)"
        ),
        {
            "name": user.name,
            "room_id": room_id,
            "user_id": user.id,
            "token": token,
            "is_host": True,
            "select_difficulty": select_difficulty.value,
        },
    )
    return room_id


def get_room_list(live_id: int) -> list[model.RoomInfo]:
    with engine.begin() as conn:
        return _get_room_list(conn, live_id)


def _get_room_list(conn, live_id: int) -> list[model.RoomInfo]:
    if live_id == 0:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `status` = :status AND `joined_user_count` < `max_user_count`"
            ),
            {"status": model.WaitRoomStatus.Waiting.value},
        )
    else:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `live_id` = :live_id AND `status` = :status AND `joined_user_count` < `max_user_count`"
            ),
            {"live_id": live_id, "status": model.WaitRoomStatus.Waiting.value},
        )
    try:
        rows = result.all()
    except NoResultFound:
        return []
    return [model.RoomInfo.from_orm(row) for row in rows]


def _get_room_by_room_id(
    conn, room_id: int, rock: bool = False
) -> Optional[model.RoomInfo]:
    query = "SELECT `live_id`, `room_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `room_id` = :room_id"
    if rock:
        query += " FOR UPDATE"
    result = conn.execute(
        text(query),
        {"room_id": room_id},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return model.RoomInfo.from_orm(row)


def join_room(
    room_id: int, select_difficulty: model.LiveDifficulty, token: str
) -> model.JoinRoomResult:
    with engine.begin() as conn:
        return _join_room(conn, room_id, select_difficulty, token)


def _join_room(
    conn, room_id: int, select_difficulty: model.LiveDifficulty, token: str
) -> model.JoinRoomResult:
    room = _get_room_by_room_id(conn, room_id, rock=True)
    if room is None:
        commit(conn)
        return model.JoinRoomResult.Disbanded

    if room.joined_user_count >= room.max_user_count:
        commit(conn)
        return model.JoinRoomResult.RoomFull

    status = _get_room_status(conn, room_id)

    if status != model.WaitRoomStatus.Waiting.value:
        commit(conn)
        return model.JoinRoomResult.OtherError

    # you are already in the room
    if not (_get_room_member_by_room_id_and_token(conn, room_id, token) is None):
        commit(conn)
        return model.JoinRoomResult.OtherError

    user = user_impl._get_user_by_token(conn, token)
    _ = conn.execute(
        text(
            "INSERT INTO `room_member` (name, room_id, user_id, token, is_host, select_difficulty) VALUES (:name, :room_id, :user_id, :token, :is_host, :select_difficulty)"
        ),
        {
            "name": user.name,
            "room_id": room_id,
            "user_id": user.id,
            "token": token,
            "is_host": False,
            "select_difficulty": select_difficulty.value,
        },
    )

    _ = conn.execute(
        text(
            "UPDATE `room` SET `joined_user_count` = `joined_user_count` + 1 WHERE `room_id` = :room_id"
        ),
        {
            "room_id": room_id,
        },
    )

    commit(conn)

    return model.JoinRoomResult.Ok


def _get_room_member_by_room_id_and_token(
    conn, room_id: int, token: str
) -> Optional[model.RoomMember]:
    result = conn.execute(
        text(
            "SELECT `name`, `room_id`, `token`, `token`, `is_host`, `select_difficulty` FROM `room_member` WHERE `room_id` = :room_id AND `token` = :token"
        ),
        {
            "room_id": room_id,
            "token": token,
        },
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return model.RoomMember.from_orm(row)


def get_room_wait(
    room_id: int, token: str
) -> tuple[model.WaitRoomStatus, list[model.RoomUser]]:
    with engine.begin() as conn:
        return _get_room_wait(conn, room_id, token)


def _get_room_wait(
    conn, room_id: int, token: str
) -> tuple[model.WaitRoomStatus, list[model.RoomUser]]:
    status = _get_room_status(conn, room_id)

    result = conn.execute(
        text(
            "SELECT `name`, `room_id`, `token`, `is_host`, select_difficulty FROM `room_member` WHERE `room_id` = :room_id"
        ),
        {
            "room_id": room_id,
        },
    )
    try:
        rows = result.all()
    except NoResultFound:
        return status, []
    room_user_list = []
    for row in rows:
        this_member = model.RoomMember.from_orm(row)
        this_user = convert_room_member_to_room_user(
            conn, this_member, is_me=(this_member.token == token)
        )
        room_user_list.append(this_user)

    return status, room_user_list


def convert_room_member_to_room_user(
    conn, room_member: model.RoomMember, is_me=True
) -> model.RoomUser:
    user = user_impl._get_user_by_token(conn, room_member.token)
    return model.RoomUser(
        user_id=user.id,
        name=room_member.name,
        leader_card_id=user.leader_card_id,
        select_difficulty=room_member.select_difficulty,
        is_host=room_member.is_host,
        is_me=is_me,
    )


def _get_room_status(conn, room_id: int) -> model.WaitRoomStatus:
    room = _get_room_by_room_id(conn, room_id)
    if room is None:
        return model.WaitRoomStatus.Dissolution

    result = conn.execute(
        text("SELECT `status` FROM `room` WHERE `room_id` = :room_id"),
        {
            "room_id": room_id,
        },
    )
    try:
        row = result.one()
    except NoResultFound:
        return model.WaitRoomStatus.OtherError
    return model.WaitRoomStatus(row[0])


def room_start(room_id: int, token: str) -> None:
    with engine.begin() as conn:
        _room_start(conn, room_id, token)


def _room_start(conn, room_id: int, token: str) -> None:
    member = _get_room_member_by_room_id_and_token(conn, room_id, token)

    if member is None:
        return

    if not member.is_host:
        return

    _ = conn.execute(
        text("UPDATE `room` SET `status` = :status WHERE `room_id` = :room_id"),
        {
            "status": model.WaitRoomStatus.LiveStart.value,
            "room_id": room_id,
        },
    )
    return


def room_end(room_id: int, judge_count_list: list[int], score: int, token: str) -> None:
    with engine.begin() as conn:
        _room_end(conn, room_id, judge_count_list, score, token)


def _room_end(
    conn, room_id: int, judge_count_list: list[int], score: int, token: str
) -> None:
    user = user_impl._get_user_by_token(conn, token)

    result = conn.execute(
        text(
            "SELECT `score` FROM `room_score` WHERE `room_id` = :room_id AND `user_id` = :user_id"
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
        },
    )

    # すでにスコアが登録されている場合はreturn(一人を保証)
    # UPDATE実装でも良い
    if result.rowcount > 0:
        return

    query1 = "INSERT INTO `room_score` (`score`, `room_id`, `user_id`"
    query2 = "VALUES (:score, :room_id, :user_id"
    d1 = {"score": score, "room_id": room_id, "user_id": user.id}

    for column, judge_count in zip(JUDGE_COLUMNS, judge_count_list):
        query1 += ", `" + column + "`"
        query2 += ", :" + column
        d1[column] = judge_count

    query1 += ") "
    query2 += ")"
    query = query1 + query2
    _ = conn.execute(text(query), d1)
    return


def get_room_result(room_id: int, token: str) -> list[model.ResultUser]:
    with engine.begin() as conn:
        return _get_room_result(conn, room_id, token)


def _get_room_result(conn, room_id: int, token: str) -> list[model.ResultUser]:
    member = _get_room_member_by_room_id_and_token(conn, room_id, token)
    room = _get_room_by_room_id(conn, room_id)
    if member is None:
        return []

    query = "SELECT `user_id`, `score`"

    for column in JUDGE_COLUMNS:
        query += ", `" + column + "`"

    query += " FROM `room_score` WHERE `room_id` = :room_id"

    result = conn.execute(
        text(query),
        {
            "room_id": room_id,
        },
    )

    if result.rowcount < room.joined_user_count:
        return []

    try:
        rows = result.all()
    except NoResultFound:
        return []

    result_user_list = []
    for row in rows:
        user = model.ResultUser(user_id=row[0], score=row[1], judge_count_list=[])
        for i in range(len(JUDGE_COLUMNS)):
            if row[i] is None:
                user.judge_count_list.append(0)
            else:
                user.judge_count_list.append(row[i + 2])
        result_user_list.append(user)
    return result_user_list


def leave_room(room_id: int, token: str) -> None:
    with engine.begin() as conn:
        _leave_room(conn, room_id, token)


def _leave_room(conn, room_id: int, token: str) -> None:
    user = user_impl._get_user_by_token(conn, token)
    if user is None:
        return

    result = conn.execute(
        text(
            "SELECT room_id, joined_user_count FROM `room` WHERE `room_id` = :room_id LOCK IN SHARE MODE"
        ),
        {
            "room_id": room_id,
        },
    )

    try:
        row = result.one()
    except NoResultFound:
        return

    room = row

    result = conn.execute(
        text(
            "SELECT user_id, room_id, token, is_host FROM `room_member` WHERE `room_id` = :room_id AND `user_id` = :user_id LOCK IN SHARE MODE"
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
        },
    )

    try:
        row = result.one()
    except NoResultFound:
        return

    member = row

    if member.is_host:
        result = conn.execute(
            text(
                "SELECT user_id FROM `room_member` WHERE `room_id` = :room_id AND `user_id` != :user_id LOCK IN SHARE MODE"
            ),
            {
                "room_id": room_id,
                "user_id": user.id,
            },
        )

        if result.rowcount > 0:
            members = result.all()
            _ = conn.execute(
                text(
                    "UPDATE `room_member` SET `is_host` = 1 WHERE `room_id` = :room_id AND `user_id` = :user_id"
                ),
                {
                    "room_id": room_id,
                    "user_id": members[0].user_id,
                },
            )

    _ = conn.execute(
        text(
            "DELETE FROM `room_member` WHERE `room_id` = :room_id AND `user_id` = :user_id"
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
        },
    )

    _ = conn.execute(
        text(
            "DELETE FROM `room_score` WHERE `room_id` = :room_id AND `user_id` = :user_id"
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
        },
    )

    _ = conn.execute(
        text(
            "UPDATE `room` SET `joined_user_count` = `joined_user_count` - 1 WHERE `room_id` = :room_id"
        ),
        {
            "room_id": room_id,
        },
    )

    room = _get_room_by_room_id(conn, room_id)
    if room.joined_user_count == 0:
        _ = conn.execute(
            text("DELETE FROM `room` WHERE `room_id` = :room_id"),
            {
                "room_id": room_id,
            },
        )

    commit(conn)

    return
