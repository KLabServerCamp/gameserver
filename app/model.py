# import json
import uuid

# from enum import Enum, IntEnum
from typing import Optional

# from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, String, select, text, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import declarative_base, relationship

from .db import engine

Base = declarative_base()


class UserTable(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    token = Column(String(255), nullable=True, unique=True)
    leader_card_id = Column(Integer, nullable=True)

    room_user = relationship("RoomUserTable", back_populates="user")


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


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


class RoomTable(Base):
    __tablename__ = "room"

    # roomid, live_id, max_user_count
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    owner_user_id = Column(Integer, nullable=False)

    room_user = relationship("RoomUserTable", back_populates="room")


class Room(BaseModel):
    id: int
    name: str
    owner_user_id: int

    class Config:
        orm_mode = True


class RoomUserTable(Base):
    __tablename__ = "room_user"

    # token, room_id
    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("room.id", onupdate="CASCADE", ondelete="CASCADE"))
    user_token = Column(String(255), ForeignKey("user.token", onupdate="CASCADE", ondelete="CASCADE"))
    select_difficulty = Column(Integer, nullable=True)

    room = relationship("RoomTable", back_populates="room_user")
    user = relationship("User", back_populates="room_user")


class RoomUser(BaseModel):
    id: int
    room_id: int
    user_token: str
    select_difficulty: int

    class Config:
        orm_mode = True


def create_room(name: str, owner_user_id: int) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                    INSERT
                        INTO
                            `room` (name, owner_user_id)
                        VALUES
                            (:name, :owner_user_id)
                """
            ),
            {"name": name, "owner_user_id": owner_user_id},
        )
        return result.lastrowid


if __name__ == "__main__":
    Base.metadata.create_all(engine)
