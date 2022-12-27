# import json
import uuid

# from enum import Enum, IntEnum
from typing import Optional

# from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, select, text, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import declarative_base

from .db import engine

Base = declarative_base()


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    token = Column(String(255), nullable=True, unique=True)
    leader_card_id = Column(Integer, nullable=True)


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
        _ = conn.execute(
            text(
                """
                    INSERT
                        INTO
                            `user` (name, token, leader_card_id)
                        VALUES
                            (:name, :token, :leader_card_id)
                """
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(f"create_user(): id={result.lastrowid} {token=}")
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    res = conn.execute(select(User).where(User.token == token))
    try:
        row = res.one()
    except NoResultFound:
        return None
    # return row
    return SafeUser(id=row.id, name=row.name, leader_card_id=row.leader_card_id)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        return _update_user(
            conn=conn, token=token, name=name, leader_card_id=leader_card_id
        )


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    _ = conn.execute(
        update(User)
        .where(User.token == token)
        .values(name=name, leader_card_id=leader_card_id)
    )

    return None
