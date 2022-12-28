# import json
import uuid

from enum import IntEnum
from typing import  Optional

# from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, String, select, text, update, insert
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import declarative_base, relationship

from app.config import MAX_USER_COUNT

from .db import engine

Base = declarative_base()

# Enum


class LiveDifficulty(IntEnum):

    easy = 1
    normal = 2


# User


class UserTable(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    token = Column(String(255), nullable=True, unique=True)
    leader_card_id = Column(Integer, nullable=True)

    room_member = relationship("RoomMemberTable", back_populates="user")


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class UserNotFound(Exception):
    """指定されたtokenに対応するユーザーが見つからなかったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    # 外部に見られてもいいもの

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
    res = conn.execute(select(UserTable).where(UserTable.token == token))
    try:
        row = res.one()
    except NoResultFound:
        return None
    # return row
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        return _update_user(conn=conn, token=token, name=name, leader_card_id=leader_card_id)


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    _ = conn.execute(update(UserTable).where(UserTable.token == token).values(name=name, leader_card_id=leader_card_id))

    return None


# Room


class RoomTable(Base):
    __tablename__ = "room"

    id = Column(Integer, primary_key=True, autoincrement=True)
    live_id = Column(Integer, nullable=True)
    max_user_count = Column(Integer, nullable=True)

    room_member = relationship("RoomMemberTable")


class Room(BaseModel):
    id: int
    live_id: int
    max_user_count: int

    class Config:
        orm_mode = True


class RoomMemberTable(Base):
    __tablename__ = "room_member"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("room.id", onupdate="CASCADE", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"))
    select_difficulty = Column(Integer, nullable=True)
    is_host = Column(Integer, nullable=True)

    room = relationship("RoomTable", back_populates="room_member", foreign_keys=[room_id])
    user = relationship("UserTable", back_populates="room_member", foreign_keys=[user_id])


class RoomMember(BaseModel):
    id: int
    room_id: int
    user_id: int
    select_difficulty: int

    class Config:
        orm_mode = True


def create_room(token: str, live_id: int, select_difficalty: LiveDifficulty) -> Optional[int]:
    with engine.begin() as conn:
        user_id = _get_user_by_token(conn, token).id
        return _create_room(conn, user_id, live_id, select_difficalty)


# TODO: 人数確認


def _create_room(conn, user_id: int, live_id: int, select_difficalty: LiveDifficulty) -> Optional[int]:

    res = conn.execute(insert(RoomTable).values(live_id=live_id, max_user_count=MAX_USER_COUNT))

    try:
        id = res.lastrowid
    except NoResultFound:
        return None

    _ = conn.execute(insert(RoomMemberTable).values(room_id=id, user_id=user_id, select_difficulty=select_difficalty))
    return id


# room 一覧
def get_room_list(live_id: int) -> list[Room]:
    with engine.begin() as conn:
        if live_id == 0:
            res = conn.execute(select(RoomTable))
        else:
            res = conn.execute(select(RoomTable).where(RoomTable.live_id == live_id))
        return [Room.from_orm(row) for row in res]


def get_room_members(room_id: int) -> list[RoomMember]:
    with engine.begin() as conn:
        res = conn.execute(select(RoomMemberTable).where(RoomMemberTable.room_id == room_id))
        return [RoomMember.from_orm(row) for row in res]


if __name__ == "__main__":
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
