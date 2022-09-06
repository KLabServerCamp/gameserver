import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound, IntegrityError

from .db import engine


# User
class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class InvalidUser(Exception):
    """オーナー以外がオーナー権が必要な操作をしたときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


# Room Enums
class LiveDifficulty(Enum):
    normal = 1
    hard = 2


class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


# Room Models
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


# User
def _user_judge(token: str) -> Optional[int]:
    user = get_user_by_token(token)
    if user is None:
        raise InvalidToken
    return user.id


def create_user(name: str, leader_card_id: int) -> Optional[str]:
    """Create new user and returns their token"""
    MAX_RETRY = 3

    with engine.begin() as conn:
        for _ in range(MAX_RETRY + 1):
            token = str(uuid.uuid4())
            try:
                conn.execute(
                    text(
                        "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
                    ),
                    dict(name=name, token=token, leader_card_id=leader_card_id),
                )
                break
            except IntegrityError:
                continue
        else:
            raise IntegrityError
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
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
        result = conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id where token=:token"
            ),
            dict(token=token, name=name, leader_card_id=leader_card_id),
        )
        print(result)


# Room
def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty) -> int:
    """Create new room and returns their id"""
    with engine.begin() as conn:
        result = conn.execute(
            text("INSERT INTO `room` (live_id) VALUES (:live_id)"),
            {"live_id": live_id},
        )
    room_id = result.lastrowid
    _create_room_member(token, room_id, select_difficulty, is_host=True)

    return room_id


def _create_room_member(
    token: str, room_id: int, select_difficulty: LiveDifficulty, is_host: bool
) -> None:
    user = get_user_by_token(token)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room_member` \
                    (room_id, user_id, name, leader_card_id, select_difficulty, is_host) \
                        VALUES \
                            (:room_id, :user_id, :name, :leader_card_id, :select_difficulty, :is_host)"
            ),
            dict(
                room_id=room_id,
                user_id=user.id,
                name=user.name,
                leader_card_id=user.leader_card_id,
                select_difficulty=select_difficulty.value,
                is_host=is_host,
            ),
        )
    print(result)


def _get_room_list(conn, live_id: int) -> Optional[list[RoomInfo]]:
    if live_id == 0:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` \
                    FROM `room` \
                    WHERE `wait_room_status`=:wait_room_status \
                        AND `joined_user_count` < `max_user_count`"
            ),
            dict(live_id=live_id, wait_room_status=WaitRoomStatus.Waiting.value),
        )
    else:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` \
                    FROM `room` \
                    WHERE `live_id`=:live_id \
                        AND `wait_room_status`=:wait_room_status \
                        AND `joined_user_count` < `max_user_count`"
            ),
            dict(live_id=live_id, wait_room_status=WaitRoomStatus.Waiting.value),
        )
    try:
        room_list = []
        for room in result:
            room_list.append(
                RoomInfo(
                    room_id=room.room_id,
                    live_id=room.live_id,
                    joined_user_count=room.joined_user_count,
                    max_user_count=room.max_user_count,
                )
            )
    except NoResultFound:
        return None
    return room_list


def get_room_list(live_id: int) -> Optional[list[RoomInfo]]:
    with engine.begin() as conn:
        return _get_room_list(conn, live_id)


def _update_room_joined_user_count(token: str, room_id: int, inc_dec_num: int) -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room` SET joined_user_count=joined_user_count + :inc_dec_num \
                    WHERE room_id=:room_id"
            ),
            dict(inc_dec_num=inc_dec_num, token=token, room_id=room_id),
        )
        print(result)


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty
) -> Optional[JoinRoomResult]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `joined_user_count`, `max_user_count`, `wait_room_status` FROM `room` \
                    WHERE `room_id`=:room_id"
            ),
            dict(room_id=room_id),
        )
        print(result)
    try:
        room = result.one()
        if room.joined_user_count >= room.max_user_count:
            return JoinRoomResult.RoomFull
        elif room.wait_room_status == WaitRoomStatus.Dissolution.value:
            return JoinRoomResult.Disbanded
    except NoResultFound:
        return JoinRoomResult.OtherError

    # 1つのトランザクションにまとめたい
    _create_room_member(token, room_id, select_difficulty, is_host=False)
    _update_room_joined_user_count(token, room_id, inc_dec_num=1)

    return JoinRoomResult.Ok


def get_room_status(token: str, room_id: int) -> Optional[WaitRoomStatus]:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `wait_room_status` FROM `room` WHERE `room_id`=:room_id"),
            dict(room_id=room_id),
        )
    return WaitRoomStatus(result.one().wait_room_status)


def get_room_user_list(token: str, room_id: int) -> Optional[list[RoomUser]]:
    user = get_user_by_token(token)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `name`, `leader_card_id`, `select_difficulty`, `is_host` \
                    FROM `room_member` WHERE `room_id`=:room_id"
            ),
            dict(room_id=room_id),
        )
    try:
        room_user_list = []
        for room_user in result:
            room_user_list.append(
                RoomUser(
                    user_id=room_user.user_id,
                    name=room_user.name,
                    leader_card_id=room_user.leader_card_id,
                    select_difficulty=room_user.select_difficulty,
                    is_me=room_user.user_id == user.id,
                    is_host=room_user.is_host,
                )
            )
    except NoResultFound:
        return None
    return room_user_list


def _is_host(room_id: int, user_id: int) -> bool:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `is_host` FROM `room_member` \
                    WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            dict(room_id=room_id, user_id=user_id),
        )
    return result.one().is_host


def start_room(token: str, room_id: int) -> None:
    user_id = _user_judge(token)
    if not _is_host(room_id, user_id):
        raise InvalidUser
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room` SET wait_room_status=:wait_room_status WHERE room_id=:room_id"
            ),
            dict(wait_room_status=WaitRoomStatus.LiveStart.value, room_id=room_id),
        )
        print(result)


def end_room(
    token: str,
    room_id: int,
    judge_count_list: list[int],
    score: int,
) -> None:
    user_id = _user_judge(token)
    judge_count_list_json = json.dumps(judge_count_list)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room_member` SET judge_count_list=:judge_count_list, score=:score \
                    WHERE room_id=:room_id AND user_id=:user_id"
            ),
            dict(
                judge_count_list=judge_count_list_json,
                score=score,
                room_id=room_id,
                user_id=user_id,
            ),
        )
        print(result)


def get_room_result(room_id: int) -> Optional[list[ResultUser]]:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `joined_user_count` FROM `room` WHERE `room_id`=:room_id"),
            dict(room_id=room_id),
        )
    joined_user_count = result.one().joined_user_count
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT COUNT(score) FROM `room_member` WHERE `room_id`=:room_id"),
            dict(room_id=room_id),
        )
    score_count = result.scalar()
    if joined_user_count == score_count:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT `user_id`, `judge_count_list`, `score` FROM `room_member` \
                        WHERE `room_id`=:room_id"
                ),
                dict(room_id=room_id),
            )
        try:
            result_user_list = []
            for result_user in result:
                result_user_list.append(
                    ResultUser(
                        user_id=result_user.user_id,
                        judge_count_list=json.loads(result_user.judge_count_list),
                        score=result_user.score,
                    )
                )
        except NoResultFound:
            return None
        return result_user_list
    else:
        return []


def _delete_room_member(token: str, room_id: int) -> None:
    user_id = _user_judge(token)
    if _is_host(room_id, user_id):
        # ホストでないユーザーを探す
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT `user_id` FROM `room_member` \
                        WHERE `room_id`=:room_id AND `is_host`=false"
                ),
                dict(room_id=room_id),
            )
            become_host = result.first()
        # 他にユーザーがいなかった場合、部屋を終了する
        if become_host is None:
            with engine.begin() as conn:
                result = conn.execute(
                    text(
                        "UPDATE `room` SET wait_room_status=:wait_room_status \
                            WHERE room_id=:room_id"
                    ),
                    dict(
                        wait_room_status=WaitRoomStatus.Dissolution.value,
                        room_id=room_id,
                    ),
                )
            return
        # ホストでないユーザー1人をホストに昇格する
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE `room_member` SET is_host=true \
                        WHERE room_id=:room_id AND user_id=:user_id"
                ),
                dict(
                    room_id=room_id,
                    user_id=become_host.user_id,
                ),
            )
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "DELETE FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            dict(room_id=room_id, user_id=user_id),
        )
    print(result)


def leave_room(token: str, room_id: int) -> None:
    _update_room_joined_user_count(token, room_id, inc_dec_num=-1)
    _delete_room_member(token, room_id)
