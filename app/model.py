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

class LiveDifficulty(Enum):
    nomal = 1
    hard = 2

class joinRoomResult(Enum):
    OK = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4

class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int 

class RoomUser(BaseModel):
    room_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host:bool

class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list
    score: int

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
    except NoResultFund:
        return None
    return SafeUser.from_orm(row)

def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def get_numofpeople_inroom_by_roomid(room_id: int) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, room_id)

def _get_numofpeople_inroom_by_roomid(conn, room_id: int) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT COUNT(`room_id` =:room_id OR NULL) FROM `room`"),
        {"room_id": room_id},
    )
    return result

def _get_username_by_userid(conn, user_id: int) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT `name`, `leader_card_id` FROM `user` WHERE `id`=:user_id"),
        {"user_id": user_id},
    )
    row = result.all()
    return row
    
def get_username_by_userid(user_id: int) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_username_by_userid(conn, user_id)

def _get_status_by_roomid(conn, room_id: int) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT `status` FROM `room` WHERE `id`=:room_id"),
        {"room_id": room_id},
    )
    row = result.one()[0]
    return row
    
def get_status_by_roomid(room_id: int) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_status_by_roomid(conn, room_id)

def _update_status_by_roomid(conn, room_id: int, status: int):
    result = conn.execute(
            text(
                "UPDATE `room` set `status`=:status where `room_id`=:room_id"
            ),
            {"status": status, "room_id": room_id},
        )
    
def update_status_by_roomid(room_id: int,status: int):
    with engine.begin() as conn:
        return _update_status_by_roomid(conn, room_id, status)
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
    # roomにユーザを登録する
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, owner, status) VALUES (:live_id, :owner, :status)"
            ),
            {"live_id": live_id, "owner": user_id, "status": 1},
        )
    room_id = result.lastrowid
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, difficulty, is_join) VALUES (:room_id, :user_id, :select_difficulty, :is_join)"
            ),
            {"room_id":room_id,
            "user_id":user_id,
            "select_difficulty":select_difficulty,
            "is_join":1},
        )
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
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT * FROM `room_member` WHERE `room_id` =:id AND `is_join` =:is_join"
                ),
                {"id": id,
                "is_join":1},
            )
            joined_user_count = len(result.all())
        print(result.all(),"eee",joined_user_count)
        tmp = RoomInfo(room_id=id,live_id=live_id,joined_user_count=joined_user_count,max_user_count=4)
        response.append(tmp)
    return response

#ルーム参加処理
def join_room(user_id:int, room_id: int, select_difficulty:int) -> Optional[joinRoomResult]:
    if get_numofpeople_inroom_by_roomid(room_id) == 4:
        update_status_by_roomid(roomid,api.joinRoomResult.RoomFull)

    #get_numofpeople_inroom_by_roomid
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, difficulty, is_join) VALUES (:room_id, :user_id, :select_difficulty, :is_join)"
            ),
            {"room_id":room_id,
            "user_id":user_id,
            "select_difficulty":select_difficulty,
            "is_join":1},
        )

    return api.joinRoomResult.Ok

#wating処理
def wait_room(room_id: int, my_user_id:int) -> Optional[RoomUser]:
    response = []
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT * FROM `room` WHERE `id` =:room_id"
            ),
            {"room_id": room_id},
        )

    owner = result.all()[0][2]

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `difficulty` FROM `room_member` WHERE `room_id` =:room_id"
            ),
            {"room_id": room_id},
        )

    for (user_id,difficulty) in result:
        is_me = False
        is_host = False
        tmp = get_username_by_userid(user_id)[0]
        name,leader_card_id = tmp
        if user_id == my_user_id:
            is_me=True
        
        if owner == my_user_id:
            is_host = False

        tmp = RoomUser(room_id=room_id,
        name=name,
        leader_card_id=leader_card_id,
        select_difficulty=difficulty,
        is_me=is_me,
        is_host=is_host)
        response.append(tmp)
    return response

def end_room(user_id:int, room_id: int, judge_count_list: list,score: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room_member` set `score`=:score, `judge`=:judge_count_list where `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {"room_id":room_id,
            "user_id":user_id,
            "score":score,
            "judge":','.join(judge_count_list)}
        )

#結果表示処理
def result_room(room_id: int) -> Optional[ResultUser]:
    response = []
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `judge_count_list`, `score` FROM `room_member` WHERE `room_id` =:room_id"
            ),
            {"room_id": room_id},
        )
    
    for (user_id, judge_count_list, score) in result:
        tmp = ResultUser(
            user_id=user_id,
            judge_count_list=list(judge_count_list.split()),
            score=score)
        response.append(tmp)
    return response

#退出処理
def leave_room(user_id:int, room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room_member` set `is_join`=:is_join, where `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {
            "is_join":0,
            "room_id":room_id,
            "user_id":user_id}
        )