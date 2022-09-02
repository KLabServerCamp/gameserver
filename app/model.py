import json
import uuid
from enum import Enum, IntEnum
from operator import le
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from app.api import JoinRoomResult, LiveDifficulty, ResultUser, RoomInfo, RoomWaitResponse, WaitRoomStatus

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
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
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


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    result = conn.execute(
        text(
            "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE token=:token"
        ),
        dict(name=name, token=token, leader_card_id=leader_card_id),
    )


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        # TODO: 実装
        return _update_user(conn, token, name, leader_card_id)


# TODO: どうにかする
MAX_USER_COUNT = 4
def create_room(live_id: int, select_difficulty: LiveDifficulty) -> int:
    """Create new user and returns their token"""
    joined_user_count = 1
    max_user_count = MAX_USER_COUNT
    
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, joined_user_count, max_user_count) VALUES (:live_id, :joined_user_count, :max_user_count)"
            ),
            {"live_id": live_id, "joined_user_count": joined_user_count, "max_user_count": max_user_count},
        )
    room_id = result.lastrowid
    return room_id

def get_room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT * FROM `room` WHERE live_id=:live_id"
            ),
            {"live_id": live_id}
        )
    room_list = list[RoomInfo]
    for row in result:
        room_list.append(
            RoomInfo(
                room_id=row.room_id,
                live_id=row.live_id,
                joined_user_count=row.joined_user_count,
                max_user_count=row.max_user_count
            )
        )
    return room_list


# def join_room(room_id: int, select_difficulty: LiveDifficulty) -> JoinRoomResult:
#     with engine.begin() as conn:
#         result = conn.execute(
#             text(
#                 "INSERTT INTO `room_member` SET \
#                     `room_id`=:room_id, \
#                     `user_id`=:user_id \
#                     `name`=:name \
#                     `leader_card_id`=:leader_card_id \
#                     `select_difficulty`=:select_difficulty \
#                     `is_me`=:is_me \
#                     `is_host`=:is_host \
#                 " 
#             ),
#             {
#                 "room_id": room_id,
#                 "user_id": user_id,
#                 "name": name,
#                 "leader_card_id": leader_card_id,
#                 "select_difficulty": select_difficulty,
#                 "is_me": is_me,
#                 "is_host": is_host
#             }
#       )

def _get_room_user(roomid: int) -> list[RoomUser]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT * FROM `room_member` WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
    room_user_list = list[RoomUser]
    for row in result:
        room_user_list.append(
            RoomUser(
                user_id=row[user_id],
                name=row[name],
                leader_card_id=row[leader_card_id],
                select_difficulty=row[select_diffculty],
                is_me=row[is_me],
                is_host=row[is_host]
            )
        )
    return room_user_list
    

def get_room_wait(room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT wait_room_status FROM `room` WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
    if len(reslut) == 0:
        return null
    assert len(result) == 1

    res = result.one
    return RoomWaitResponse(
        wait_room_status=res[wait_room_status]
        room_user_list = _get_room_user(room_id)
    )
    
def update_wait_room_status(room_id: int, wait_room_status: WaitRoomStaus):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room` SET wait_room_status=:wait_room_status WHERE room_id=:room_id"
            ),
            {"wait_room_status": wait_room_status, "room_id": room_id}
        )

# TODO: 実装途中
def post_result(room_id: int, result_user: ResultUser):
    with engine.begin() as conn:
        result = conn.execute(
            # TODO: judge_count_listの扱いどうしよう
            text(
                "UPDATE `room_member` SET \
                    \
                    WHERE room_id=:room_id AND user_id=:user_id"
            ),
            # TODO: 中身入れる
            {}
        )

def end_room(user_id: int, room_id: int, judge_count_list: list[int], score: int): 
    post_result(room_id, ResultUser("user_id": user_id, "judge_count_list": judge_count_list, "score": score)) 
    update_wait_room_status(room_id, WaitRoomStatus.Dissolution)
    
def get_result_user_list(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        result = conn.execute(
            # TODO: judge_count_listの扱いどうしよう
            text(
                "SELECT `user_id`, `judge_count_list`, `score` FROM room_member WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
    result_user_list: list[ResultUser]
    for row in result:
        result_user_list.append(
            ResultUser(
                user_id=user_id,
                judge_count_lsit=judge_count_list,
                score=score
            )
        )
    return result_user_list
