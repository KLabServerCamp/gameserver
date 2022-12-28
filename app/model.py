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


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `user` set `name`=:name, `leader_card_id`=:leader_card_id where `token`=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )

#live_id user_idからroom_idを得る
def get_room_id_by_live_id_and_user_id(live_id: int, user_id int):
    result = conn.execute(
        text("SELECT `id` FROM `room` WHERE `live_id`=:live_id AND `user_id`=:user_id"),
        {"live_id": live_id,"user_id":user_id},
    )
    try:
        row = result.one()
    except NoResultFpund:
        return None
    return SafeUser.from_orm(row)

#ルーム作成DB操作
def create_room(token: str,live_id: int, select_difficulty: int) -> int:
    """Create new room and returns room id"""
    user_id = get_user_by_token(token)
    #roomにユーザを登録する
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id,owner) VALUES (:live_id, :user_id) RETURNING id"
            ),
            {"live_id": live_id,"owner":user_id},
        )
    print(result)
    
    # #作成したルームのIDを得る
    # room_id 
    # #作成したルームのIDと同じカラムをroom_memberテーブルに作る
    # with engine.begin() as conn:
    #     result = conn.execute(
    #         text(
    #             "INSERT INTO `room_member` (live_id,owner) VALUES (:live_id, :user_id)"
    #         ),
    #         {"live_id": live_id},
    #     )

    