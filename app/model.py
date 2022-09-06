import logging
import uuid
from enum import IntEnum, auto
from typing import Optional, Union

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from . import config
from .db import engine

logger = logging.getLogger("app.model")


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
        conn: Connection
        query_str: str = "\
            INSERT INTO `user` SET \
                `name` = :name, \
                `leader_card_id` = :leader_id, \
                `token` = :token \
            "

        result = conn.execute(
            text(query_str),
            {"name": name, "token": token, "leader_id": leader_card_id},
        )
        logger.debug(result)
    return token


def _get_user_by_token(conn: Connection, token: str) -> Optional[SafeUser]:
    query_str: str = "\
        SELECT `id`, `name`, `leader_card_id` \
        FROM `user` \
        WHERE `token`=:token"

    result = conn.execute(text(query_str), {"token": token})
    if row := result.one_or_none():
        logger.debug(row)
        return SafeUser.from_orm(row)
    return None


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        conn: Connection
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        conn: Connection
        if _ := _get_user_by_token(conn, token):
            query_str: str = "\
                UPDATE `user` SET \
                    `name` = :name, \
                    `leader_card_id` = :leader_id \
                WHERE `token` = :token"

            conn.execute(
                text(query_str),
                {"name": name, "leader_id": leader_card_id, "token": token},
            )

            return
        raise InvalidToken()


# Room


class LiveDifficulty(IntEnum):
    """ライブの難易度

    - NORMAL: 普通
    - HARD: ハード
    """

    NORMAL = auto()
    HARD = auto()


class JoinRoomResult(IntEnum):
    """部屋に参加した結果

    - SUCCESS: 成功
    - ROOM_FULL: 部屋が満員
    - DISBANDED: 部屋が解散済み
    - OTHER_ERROR: その他のエラー
    """

    OK = auto()
    ROOM_FULL = auto()
    DISBANDED = auto()
    OTHER_ERROR = auto()


class WaitRoomStatus(IntEnum):
    """待機部屋の状態

    - WAITING: ホストがライブ開始ボタン押すのを待っている
    - STARTED: ライブ画面遷移OK
    - DISBANDED: 部屋が解散した
    """

    WAITING = auto()
    STARTED = auto()
    DISSOLUTION = auto()


class RoomInfo(BaseModel):
    """部屋の情報

    - room_id (int): 部屋識別子
    - live_id (int): プレイ対象の楽曲識別子
    - join_user_count (int): 部屋に参加しているユーザーの数
    - max_user_count (int): 部屋の最大人数
    """

    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    """部屋に参加しているユーザーの情報

    - user_id (int): ユーザー識別子
    - name (str): ユーザー名
    - leader_card_id (int): リーダーカードの識別子
    - selected_difficulty (LiveDifficulty): 選択した難易度
    - is_host (bool): 部屋のホストかどうか
    """

    user_id: int  # ユーザー識別子
    name: str  # ユーザー名
    leader_card_id: int  # リーダーカードの識別子
    select_difficulty: LiveDifficulty  # 選択難易度
    is_me: bool  # リクエストを投げたユーザーか
    is_host: bool  # 部屋を立てた人か

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    """結果画面に表示するユーザーの情報

    - user_id (int): ユーザー識別子
    - judge_count_list (List[int]): 各難易度での判定数
    - score (int): スコア
    """

    user_id: int  # ユーザー識別子
    judge_count_list: list[int]  # 各判定の数 ()
    score: int  # 獲得スコア


def _get_room_info(conn: Connection, room_id: int) -> Optional[RoomInfo]:
    query_str: str = " \
        SELECT \
            `room`.`id` AS `room_id`, \
            `room`.`live_id`, \
            COUNT(`room_user`.`user_id`) AS `joined_user_count`, \
            `room`.`max_user` AS `max_user_count` \
        FROM `room` \
        LEFT JOIN `room_user` \
            ON `room`.`id` = `room_user`.`room_id` \
        WHERE `room`.`id` = :room_id \
        GROUP BY `room`.`id` \
        FOR UPDATE"

    result = conn.execute(text(query_str), {"room_id": room_id})
    if row := result.one_or_none():
        return RoomInfo.from_orm(row)
    return None


def _set_room_status(
    conn: Connection,
    room_id: int,
    status: WaitRoomStatus,
) -> None:
    query_str: str = "\
        UPDATE `room` \
        SET `status`=:status \
        WHERE `id`=:room_id"
    conn.execute(text(query_str), {"status": status.value, "room_id": room_id})


def _get_host_id(conn: Connection, room_id: int) -> int:
    query_str: str = "SELECT `host_id` FROM `room` WHERE `id`=:room_id"
    result = conn.execute(text(query_str), {"room_id": room_id})
    if host := result.one_or_none():
        return host[0]
    raise HTTPException(status_code=404, detail="Room not found")


def _get_room_user_list(
    conn: Connection,
    room_id: int,
    uid: int,
) -> list[RoomUser]:
    query_str: str = "\
        SELECT  \
            `user`.`id` AS user_id, \
            `user`.`name`, \
            `user`.`leader_card_id`, \
            `room_user`.`difficulty` AS select_difficulty, \
            (`user`.`id` = :uid) AS is_me, \
            (`user`.`id` = :host_id) AS is_host \
        FROM `room_user` \
        INNER JOIN `user` ON `room_user`.`user_id` = `user`.`id` \
        WHERE `room_user`.`room_id` = :room_id"

    host_id = _get_host_id(conn, room_id)
    result = conn.execute(
        text(query_str),
        {"uid": uid, "host_id": host_id, "room_id": room_id},
    ).all()
    return [RoomUser.from_orm(row) for row in result]


def _add_room_user(
    conn: Connection,
    room_id: int,
    uid: int,
    difficulty: LiveDifficulty,
) -> JoinRoomResult:
    if room := _get_room_info(conn, room_id):
        if room.max_user_count <= room.joined_user_count:
            return JoinRoomResult.ROOM_FULL

        if room.joined_user_count == (room.max_user_count - 1):
            _set_room_status(conn, room_id, WaitRoomStatus.ROOM_FULL)

        query_str: str = "\
            INSERT INTO `room_user` SET \
                `room_id` = :room_id, \
                `user_id` = :user_id, \
                `difficulty` = :difficulty \
            "

        conn.execute(
            text(query_str),
            {
                "room_id": room_id,
                "user_id": uid,
                "difficulty": difficulty.value,
            },
        )

        return JoinRoomResult.OK
    return JoinRoomResult.OTHER_ERROR


def create_room(token: str, live_id: int, duffuculty: LiveDifficulty) -> int:
    with engine.begin() as conn:
        conn: Connection
        if user := _get_user_by_token(conn, token):
            query_str: str = "\
                INSERT INTO `room` SET  \
                    `live_id` = :live_id, \
                    `host_id` = :host_id, \
                    `status` = :status, \
                    `max_user` = :max_user \
                "

            result = conn.execute(
                text(query_str),
                {
                    "live_id": live_id,
                    "host_id": user.id,
                    "status": WaitRoomStatus.WAITING.value,
                    "max_user": config.MAX_ROOM_USER_COUNT,
                },
            )

            room_id: int = result.lastrowid
            _add_room_user(conn, room_id, user.id, duffuculty)
            return room_id
        raise InvalidToken


def get_waiting_room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        conn: Connection
        query_str: str
        query_args: dict[str, Union[str, int]]

        query_str = "\
            SELECT `id` FROM `room` \
            WHERE `status`=:status \
            FOR UPDATE"
        query_args = {"status": WaitRoomStatus.WAITING.value}

        if live_id != 0:
            query_str = "\
                SELECT `id` FROM `room` \
                WHERE `live_id`=:live_id AND `status`=:status \
                FOR UPDATE"
            query_args.update({"live_id": live_id})

        result = conn.execute(text(query_str), query_args)
        return [x for x in [_get_room_info(conn, row["id"]) for row in result] if x]


def join_room(
    token: str,
    room_id: int,
    difficulty: LiveDifficulty,
) -> JoinRoomResult:
    with engine.begin() as conn:
        conn: Connection
        if user := _get_user_by_token(conn, token):
            return _add_room_user(conn, room_id, user.id, difficulty)
        raise InvalidToken


def wait_room(
    token: str,
    room_id: int,
) -> tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        conn: Connection
        if user := _get_user_by_token(conn, token):
            user_list = _get_room_user_list(conn, room_id, user.id)
            if len(user_list) < 1:
                _set_room_status(conn, room_id, WaitRoomStatus.DISSOLUTION)
                return (WaitRoomStatus.DISSOLUTION, user_list)

            query_str: str = "\
                SELECT `status` \
                FROM `room` \
                WHERE `id`=:room_id \
                FOR UPDATE"

            result = conn.execute(text(query_str), {"room_id": room_id})
            if row := result.one_or_none():
                return (WaitRoomStatus(row[0]), user_list)

            raise HTTPException(status_code=404, detail="Room not found")
        raise InvalidToken


def start_live(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        conn: Connection
        if user := _get_user_by_token(conn, token):
            host = _get_host_id(conn, room_id)
            if user.id == host:
                count: int = len(_get_room_user_list(conn, room_id, user.id))
                query_str: str = "\
                    UPDATE `room` SET \
                        `status` = :status, \
                        `live_member` = :count \
                    WHERE `id`=:room_id \
                "

                conn.execute(
                    text(query_str),
                    {
                        "status": WaitRoomStatus.STARTED.value,
                        "count": count,
                        "room_id": room_id,
                    },
                )
            logger.warning("User %s is not host", user.id)
            return
        raise InvalidToken


def end_live(token: str, room_id: int, judge: str, score: int) -> None:
    with engine.begin() as conn:
        conn: Connection
        if user := _get_user_by_token(conn, token):
            query_str: str = "\
                UPDATE `room_user` SET \
                    `judge`=:judge, \
                    `score`=:score \
                WHERE `room_id`=:room_id AND `user_id`=:user_id"
            logger.debug(judge)

            conn.execute(
                text(query_str),
                {
                    "judge": judge,
                    "score": score,
                    "room_id": room_id,
                    "user_id": user.id,
                },
            )

            return
        raise InvalidToken


def get_room_result(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        conn: Connection
        query_str: str

        query_str = "\
            SELECT \
                `user`.`id`, \
                `room_user`.`judge` AS judge_count_list, \
                `room_user`.`score` \
            FROM `room_user` \
            INNER JOIN `user` ON `room_user`.`user_id` = `user`.`id` \
            WHERE `room_user`.`room_id` = :room_id \
        "

        result = conn.execute(
            text(query_str),
            {"room_id": room_id},
        ).all()

        ret = [
            ResultUser(
                user_id=row[0],
                judge_count_list=[int(x) for x in row[1].split(",")],
                score=row[2],
            )
            for row in result
            if row["judge_count_list"] and row["score"]
        ]

        query_str = "\
            SELECT \
                TIMESTAMPDIFF(SECOND, \
                    `created_at`, \
                    CURRENT_TIMESTAMP \
                ) AS timespan, \
                `live_member` \
            FROM `room` \
            WHERE `id` = :room_id \
        "
        creation_data = conn.execute(
            text(query_str),
            {"room_id": room_id},
        ).one()
        logger.debug(creation_data)

        is_timeout = 60 * config.RESULT_TIMEOUT_MIN < creation_data["timespan"]
        if not is_timeout and (len(ret) < creation_data["live_member"]):
            logger.debug(result)
            return list[ResultUser]()
        _set_room_status(conn, room_id, WaitRoomStatus.DISSOLUTION)
        return ret


def leave_room(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        conn: Connection
        if user := _get_user_by_token(conn, token):
            query_str: str

            user_list = _get_room_user_list(conn, room_id, user.id)

            if len(user_list) < 2:
                # 自分が一人だったら部屋を解散状態にする
                _set_room_status(conn, room_id, WaitRoomStatus.DISSOLUTION)

            else:
                host = _get_host_id(conn, room_id)
                if user.id == host:
                    # 自分が部屋のホストだったらホストを変更する
                    query_str = "\
                        UPDATE `room` SET \
                            `host_id` = :host_id \
                        WHERE `id`=:room_id \
                    "

                    room_user: RoomUser
                    while room_user := user_list.pop():
                        if room_user.user_id != user.id:
                            break

                    conn.execute(
                        text(query_str),
                        {
                            "host_id": room_user.user_id,
                            "room_id": room_id,
                        },
                    )

            query_str = "\
                DELETE FROM `room_user` \
                WHERE `room_id`=:room_id AND `user_id`=:user_id \
            "

            conn.execute(
                text(query_str),
                {"room_id": room_id, "user_id": user.id},
            )

            return
        raise InvalidToken
