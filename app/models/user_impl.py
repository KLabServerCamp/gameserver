import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from ..config import JUDGE_COLUMNS, MAX_USER_COUNT
from ..db import engine
from . import model


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        while not (_get_user_by_token(conn, token) is None):
            token = str(uuid.uuid4())
        _ = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
    return token


def _get_user_by_token(conn, token: str) -> Optional[model.SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token` = :token"
        ),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return model.SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[model.SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        # TODO: 実装
        return _update_user(conn, token, name, leader_card_id)


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    result = conn.execute(
        text(
            "UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id WHERE `token` = :token"
        ),
        {"name": name, "leader_card_id": leader_card_id, "token": token},
    )
    return
