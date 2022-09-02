import json
import logging
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
                "INSERT INTO `user` (name, token, leader_card_id) \
                    VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        logging.log(logging.DEBUG, result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    query_str: str = "SELECT `id`, `name`, `leader_card_id` \
            FROM `user` \
            WHERE `token`=:token"

    result = conn.execute(text(query_str), {"token": token})
    try:
        return SafeUser.from_orm(result.one())
    except NoResultFound:
        return None


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        query_str: str = "UPDATE `user` \
            SET `name` = :name, `leader_card_id` = :leader_id \
            WHERE `token` = :token"

        result = conn.execute(
            text(query_str),
            {"name": name, "leader_id": leader_card_id, "token": token},
        )
        logging.log(logging.DEBUG, result)
