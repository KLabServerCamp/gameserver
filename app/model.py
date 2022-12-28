import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

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

class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int 

class LiveDifficulty(Enum):
    nomal = 1
    hard = 2

class joinRoomResult(Enum):
    OK = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4

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
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFpund:
        return None
    return SafeUser.from_orm(row)


def get_numofpeople_inroom_by_roomid(room_id: int) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, room_id)

def _get_numofpeople_inroom_by_roomid(conn, room_id: int) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT COUNT(`room_id` =:room_id OR NULL) FROM `room`"),
        {"room_id": room_id},
    )
    print(result)
    return result


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)

##############


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `user` set `name`=:name, `leader_card_id`=:leader_card_id where `token`=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )

# ルーム作成DB操作
def create_room(user_id: int, live_id: int, select_difficulty: int) -> int:
    """Create new room and returns room id"""
    print(user_id,live_id,select_difficulty,"rrr")
    # roomにユーザを登録する
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, owner, status) VALUES (:live_id, :owner, :status)"
            ),
            {"live_id": live_id, "owner": user_id, "status": 1},
        )
    room_id = result.lastrowid
    return room_id

# ルーム検索DB操作
def search_room(live_id: int) -> Optional[RoomInfo]:
    """Returns room id list"""
    response = []
    if live_id == 0:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT * FROM `room`"
                )
            )
    else:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT * FROM `room` WHERE `live_id` =:live_id"
                ),
                {"live_id": live_id},
            )

    for (id,live_id,owner,status) in result:
        tmp = RoomInfo(room_id=id,live_id=live_id,joined_user_count=1,max_user_count=4)
        response.append(tmp)
    return response

#ルーム参加処理
def join_room(user_id:int, room_id: int) -> Optional[joinRoomResult]:
    if get_numofpeople_inroom_by_roomid >= 4:
        return joinRoomResult(RoomFull)

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, owner, status) VALUES (:live_id, :owner, :status)"
            ),
            {"live_id": live_id, "owner": user_id, "status": 1},
        )
    room_id = result.lastrowid
    return room_id

    return joinRoomResult(result)