# import json
import uuid

from enum import Enum
# from enum import IntEnum
from typing import Optional

# from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from app.db import engine


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
    normal = 1
    hard = 2


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        _ = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id)"
                + " VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    """fetch user data"""
    result = conn.execute(
        text("SELECT * FROM `user` WHERE `token` = :token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return row


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def _get_user(conn) -> Optional[SafeUser]:
    """fetch user data"""
    # TODO: 実装
    result = conn.execute(
        text("SELECT * FROM `user`"),
    )
    try:
        for row in result:
            print(row)

    except NoResultFound:
        return None
    # print(result)
    return None


def get_user() -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user(conn)


def _update_user_by_token(
    conn, token: str, name: str, leader_card_id: str
) -> Optional[SafeUser]:
    """update user data"""
    # TODO: 実装
    _ = conn.execute(
        text(
            "UPDATE `user` SET"
            + " `name`= :name,"
            + "`leader_card_id`= :leader_card_id"
            + " WHERE `token` = :token"
        ),
        {"name": name, "leader_card_id": leader_card_id, "token": token},
    )
    return


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # tokenベースでnameとleader_card_idを変更
    with engine.begin() as conn:
        return _update_user_by_token(conn, token, name, leader_card_id)


def _create_room(
    conn, token: str, live_id: int, select_difficulty: LiveDifficulty
) -> int:
    result = _get_user_by_token(conn, token)
    user_id = result.id
    result2 = conn.execute(
        text(
            "INSERT INTO `room`"
            + " (live_id, host_user_id, status,"
            + " joined_user_count, max_user_count)"
            + " VALUES (:live_id, :host_user_id, :status,"
            + " :joined_user_count, :max_user_count)"
        ),
        {
            "live_id": live_id, "host_user_id": user_id, "status": 1,
            "joined_user_count": 0, "max_user_count": 4
        },
    )
    room_id = result2.lastrowid
    _ = _join_room(conn, token, room_id, select_difficulty)
    return room_id


def create_room(
    token: str, live_id: int, select_difficulty: LiveDifficulty
) -> int:
    """Create new room and returns its id"""
    with engine.begin() as conn:
        return _create_room(conn, token, live_id, select_difficulty)


def _list_room(
    conn, token: str, live_id: int
) -> dict:
    if live_id != 0:
        result = conn.execute(
            text(
                "SELECT id, live_id, host_user_id,"
                + " joined_user_count, max_user_count"
                + " FROM `room`"
                + " WHERE live_id = :live_id"
                + " AND joined_user_count < max_user_count"
                + " AND status = 1"
            ),
            {"live_id": live_id},
        )
    else:
        # live_id == 0 はワイルドカード
        result = conn.execute(
            text(
                "SELECT id, live_id, host_user_id,"
                + " joined_user_count, max_user_count"
                + " FROM `room`"
                + " WHERE joined_user_count < max_user_count"
                + " AND status = 1"
            ),
            {"live_id": live_id},
        )
    output = []
    for row in result:
        output.append(
            dict(
                room_id=row.id,
                live_id=row.live_id,
                host_user_id=row.host_user_id,
                joined_user_count=row.joined_user_count,
                max_user_count=row.max_user_count
            )
        )
    return output


def list_room(token: str, live_id: int) -> dict:
    with engine.begin() as conn:
        return _list_room(conn, token, live_id)


def _join_room(
    conn, token: str, room_id: int, select_difficulty: LiveDifficulty
) -> int:
    result = _get_user_by_token(conn, token)
    user_id = result.id
    # 部屋人数チェック
    result2 = conn.execute(
        text(
            "SELECT joined_user_count, max_user_count, status"
            + " FROM `room` WHERE `id` = :room_id FOR UPDATE"
        ),
        {"room_id": room_id},
    )
    try:
        elements = result2.one()
        status = elements.status
        joined_user_count = elements.joined_user_count
        max_user_count = elements.max_user_count
    except Exception as e:
        print("エラー文", e)
        return 4
    if joined_user_count >= max_user_count:
        return 2
    elif status == 3:
        return 3
    _ = conn.execute(
        text(
            "INSERT INTO `room_member` (room_id, user_id, score,"
            + "judge_perfect, judge_great, judge_good,"
            + " judge_bad, judge_miss, select_difficulty)"
            + " VALUES (:room_id, :user_id, NULL,"
            + " NULL, NULL, NULL,"
            + " NULL, NULL, :select_difficulty)"
        ),
        {
            "room_id": room_id, "user_id": user_id,
            "select_difficulty": select_difficulty.value
        },
    )
    _ = conn.execute(
        text(
            "UPDATE `room` SET"
            + " `joined_user_count`= :joined_user_count"
            + " WHERE `id` = :room_id; COMMIT"
        ),
        {"room_id": room_id, "joined_user_count": joined_user_count+1},
    )
    return 1


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty
) -> int:
    """Create new room and returns its id"""
    with engine.begin() as conn:
        return _join_room(conn, token, room_id, select_difficulty)


def _wait_room(conn, room_id: int, token: str) -> int:
    result = conn.execute(
        text(
            "SELECT host_user_id, status, joined_user_count FROM room"
            + " WHERE id = :room_id"
        ),
        {"room_id": room_id},
    )
    element = result.one()
    host_user_id = element.host_user_id
    status = element.status
    joined_user_count = element.joined_user_count
    result = _get_user_by_token(conn, token)
    my_user_id = result.id

    result2 = conn.execute(
        text(
            "SELECT user_id, name, leader_card_id, select_difficulty,"
            + " CASE WHEN user_id = :my_user_id THEN 1 ELSE 0 END AS is_me,"
            + " CASE WHEN user_id = :host_user_id THEN 1 ELSE 0 END AS is_host"
            + " FROM"
            + " (SELECT user_id, select_difficulty FROM room_member"
            + " WHERE room_id = :room_id) AS _room_member"
            + " LEFT OUTER JOIN"
            + " (SELECT id, name, leader_card_id FROM user) AS _user"
            + " ON _user.id = _room_member.user_id"
        ),
        {
            "my_user_id": my_user_id,
            "host_user_id": host_user_id,
            "room_id": room_id
        },
    )
    room_user_list = result2.all()
    return [status, room_user_list[0:joined_user_count]]


def wait_room(room_id: int, token: str) -> int:
    with engine.begin() as conn:
        return _wait_room(conn, room_id, token)


def _start_room(conn, room_id: int):
    _ = conn.execute(
        text(
            "UPDATE `room` SET `status`= :status"
            + " WHERE `id` = :room_id"
        ),
        {"room_id": room_id, "status": 2},
    )
    return


def start_room(room_id: int):
    with engine.begin() as conn:
        return _start_room(conn, room_id)


def _end_room(
    conn, room_id: int, judge_count_list: list[int], score: int, token: str
):
    result = _get_user_by_token(conn, token)
    my_user_id = result.id
    _ = conn.execute(
        text(
            "UPDATE `room_member`"
            + " SET `judge_perfect`= :judge_perfect,"
            + " `judge_great`= :judge_great,"
            + " `judge_good`= :judge_good,"
            + " `judge_bad`= :judge_bad,"
            + " `judge_miss`= :judge_miss,"
            + " `score`= :score"
            + " WHERE `room_id` = :room_id"
            + " AND `user_id` = :my_user_id"
        ),
        {
            "judge_perfect": judge_count_list[0],
            "judge_great": judge_count_list[1],
            "judge_good": judge_count_list[2],
            "judge_bad": judge_count_list[3],
            "judge_miss": judge_count_list[4],
            "score": score,
            "room_id": room_id,
            "my_user_id": my_user_id
        },
    )
    return


def end_room(
    room_id: int, judge_count_list: list[int], score: int, token: str
):
    with engine.begin() as conn:
        return _end_room(conn, room_id, judge_count_list, score, token)


def _result_room(conn, room_id: int):
    result = conn.execute(
        text(
            "SELECT user_id, judge_perfect, judge_great, judge_good,"
            + " judge_bad, judge_miss, score"
            + " FROM room_member WHERE `room_id` = :room_id"
        ),
        {
            "room_id": room_id
        },
    )
    rows = result.all()

    result2 = conn.execute(
        text(
            "SELECT joined_user_count"
            + " FROM `room` WHERE `id` = :room_id"
        ),
        {"room_id": room_id},
    )
    elements = result2.one()
    joined_user_count = elements.joined_user_count

    # 終了人数の確認、部屋状態の更新
    finish = 0
    for row in rows:
        if row.score is not None:
            finish += 1
    if finish == joined_user_count:
        _ = conn.execute(
            text(
                "UPDATE `room`"
                + " SET `status`= :status"
                + " WHERE `id` = :room_id"
            ),
            {
                "status": 3,
                "room_id": room_id
            },
        )
        return rows
    else:
        return []


def result_room(room_id: int):
    with engine.begin() as conn:
        return _result_room(conn, room_id)


def _leave_room(conn, room_id: int, token: str):
    result = _get_user_by_token(conn, token)
    my_user_id = result.id
    result2 = conn.execute(
        text(
            "SELECT host_user_id"
            + " FROM `room` WHERE `id` = :room_id"
        ),
        {"room_id": room_id},
    )
    try:
        elements = result2.one()
        host_user_id = elements.host_user_id
    except Exception as e:
        print("エラー文", e)
        return
    _ = conn.execute(
        text(
            "DELETE FROM room_member"
            + " WHERE `room_id` = :room_id"
            + " AND `user_id` = :user_id"
        ),
        {
            "room_id": room_id,
            "user_id": my_user_id
        },
    )
    _ = conn.execute(
        text(
            "UPDATE `room`"
            + " SET `joined_user_count` = `joined_user_count`-1"
            + " WHERE `id` = :room_id"
        ),
        {
            "room_id": room_id
        },
    )
    if my_user_id == host_user_id:
        result3 = conn.execute(
            text(
                "SELECT user_id"
                + " FROM `room_member` WHERE `room_id` = :room_id"
            ),
            {"room_id": room_id},
        )
        try:
            # ホスト移行処理
            _post_host_user_id = result3.one()
            post_host_user_id = _post_host_user_id.user_id
            _ = conn.execute(
                text(
                    "UPDATE `room`"
                    + " SET `host_user_id`= :post_host_user_id,"
                    + " `status` = :status"
                    + " WHERE `room_id` = :room_id"
                ),
                {
                    "post_host_user_id": post_host_user_id,
                    "status": 1,
                    "room_id": room_id
                },
            )
        except NoResultFound:
            # 部屋解散処理
            _ = conn.execute(
                text(
                    "UPDATE `room`"
                    + " SET `status` = :status"
                    + " WHERE `id` = :room_id"
                ),
                {"status": 3, "room_id": room_id},
            )
        except Exception as e:
            print("エラー文", e)
            return
    return


def leave_room(room_id: int, token: str):
    with engine.begin() as conn:
        return _leave_room(conn, room_id, token)
