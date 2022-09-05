import json
import uuid
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from ..db import engine
from .base import *


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
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `token`, `leader_card_id` FROM `user` WHERE `token`=:token"
        ),
        dict(token=token),
    )
    try:
        row = result.one()
    except NoResultFound as e:
        return None

    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def validUser(token: str):
    usr = get_user_by_token(token)
    if usr is None:
        raise HTTPException(status_code=401)
    return usr


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    # tokenは不変
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE token=:token"
            ),
            dict(name=name, leader_card_id=leader_card_id, token=token),
        )
