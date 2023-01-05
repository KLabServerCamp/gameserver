import sys
import time
from enum import IntEnum
from typing import Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

sys.path.append("./")
import app.model as model
from app.db import engine
from app.model import SafeUser

max_user_count = 4


class LiveDifficulty(IntEnum):
    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Wating = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


def _create_room(
    conn, live_id: int, select_difficulty: LiveDifficulty, user: SafeUser
) -> int:

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `room` (live_id, owner_id, status) "
                "VALUES (:live_id, :owner_id, :status)"
            ),
            {
                "live_id": live_id,
                "owner_id": user.id,
                "status": WaitRoomStatus.Wating.value,
            },
        )

        result = conn.execute(
            text(
                "SELECT `room_id` FROM `room` "
                "WHERE `owner_id` = :owner_id AND `status` NOT IN (:status)"
            ),
            {"owner_id": user.id, "status": WaitRoomStatus.Dissolution.value},
        )
        row = result.one()

        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, select_difficulty) "
                "VALUES (:room_id, :user_id, :select_difficulty)"
            ),
            {
                "room_id": row.room_id,
                "user_id": user.id,
                "select_difficulty": select_difficulty.value,
            },
        )

        return row


def create_room(live_id: int, select_difficulty: LiveDifficulty, token: str) -> int:
    with engine.begin() as conn:
        user = model._get_user_by_token(conn, token)
        if user is None:
            raise HTTPException(status_code=404)

        return _create_room(conn, live_id, select_difficulty, user)


# RoomInfoの取得
def get_room_info(conn, room_id: int, live_id: int) -> RoomInfo:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `user_id` FROM `room_member` WHERE `room_id` = :room_id"),
            {"room_id": room_id},
        )

        user_count = len(result.all())

        if user_count < max_user_count:
            return RoomInfo(
                room_id=room_id,
                live_id=live_id,
                joined_user_count=user_count,
                max_user_count=max_user_count,
            )
        else:
            return None


# room_listの取得
def _get_room_list(conn, live_id: int) -> Optional[list[RoomInfo]]:
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text("SELECT `room_id`, `live_id`, `status` FROM `room`"),
                {},
            )
        else:
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `status` FROM `room` "
                    "WHERE `live_id` = :live_id"
                ),
                {"live_id": live_id},
            )

        try:
            rows = result.all()
        except NoResultFound:
            return []

        room_info_list = []

        for row in rows:
            if row.status == WaitRoomStatus.Wating:
                room_info = get_room_info(conn, row.room_id, row.live_id)
                if room_info is not None:
                    room_info_list.append(room_info)

        return room_info_list


def get_room_list(live_id: int) -> Optional[list[RoomInfo]]:
    with engine.begin() as conn:
        return _get_room_list(conn, live_id)


# ルームの状態を確認
def room_status_check(conn, room_id: int) -> Optional[WaitRoomStatus]:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id` = :room_id FOR UPDATE"),
            {"room_id": room_id},
        )

        try:
            room_status = result.one().status
        except NoResultFound:
            return WaitRoomStatus.Dissolution

        return room_status


# ルームに入場する
def _room_join(
    conn, room_id: int, select_difficulty: LiveDifficulty, user_id: int
) -> Optional[JoinRoomResult]:

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id` FROM `room_member` "
                "WHERE `room_id` = :room_id FOR UPDATE"
            ),
            {"room_id": room_id},
        )

        if len(result.all()) > max_user_count - 1:
            return JoinRoomResult.RoomFull

        result = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, select_difficulty) "
                "VALUES (:room_id, :user_id, :select_difficulty)"
            ),
            {
                "room_id": room_id,
                "user_id": user_id,
                "select_difficulty": select_difficulty.value,
            },
        )

        try:
            res = result
        except NoResultFound:
            return JoinRoomResult.OtherError
        return JoinRoomResult.Ok


def room_join(
    room_id: int, select_difficulty: LiveDifficulty, token: str
) -> Optional[JoinRoomResult]:

    with engine.begin() as conn:
        if room_status_check(conn, room_id) == WaitRoomStatus.Dissolution:
            return JoinRoomResult.Disbanded

        user = model._get_user_by_token(conn, token)
        if user is None:
            return JoinRoomResult.OtherError

        return _room_join(conn, room_id, select_difficulty, user.id)


# ルーム内のユーザの確認
def user_check(
    conn,
    room_id: int,
    req_user_id: int,
    user_id: int,
    select_difficulty: LiveDifficulty,
) -> Optional[RoomUser]:
    with engine.begin() as conn:
        is_host = False
        is_me = False

        result = conn.execute(
            text("SELECT `owner_id` FROM `room` WHERE `room_id` = :room_id"),
            {"room_id": room_id},
        )
        row = result.one()
        if user_id == row.owner_id:
            is_host = True

        result = conn.execute(
            text("SELECT `name`, `leader_card_id` FROM `user` WHERE `id` = :user_id"),
            {"user_id": user_id},
        )
        row = result.one()
        if req_user_id == user_id:
            is_me = True

        return RoomUser(
            user_id=user_id,
            name=row.name,
            leader_card_id=row.leader_card_id,
            select_difficulty=select_difficulty,
            is_me=is_me,
            is_host=is_host,
        )


# ルーム待機
def _room_wait(
    conn, room_id: int, user: SafeUser
) -> Tuple[WaitRoomStatus, list[RoomUser]]:

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `select_difficulty` FROM `room_member` "
                "WHERE `room_id` = :room_id FOR UPDATE"
            ),
            {"room_id": room_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return (WaitRoomStatus.Dissolution, None)

        user_list = [
            user_check(conn, room_id, user.id, row.user_id, row.select_difficulty)
            for row in rows
        ]

        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id` = :room_id FOR UPDATE"),
            {"room_id": room_id},
        )

        row = result.one()

        if row.status == WaitRoomStatus.LiveStart:
            return (WaitRoomStatus.LiveStart, user_list)
        else:
            return (WaitRoomStatus.Wating, user_list)


def room_wait(room_id: int, token: str) -> Tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        user = model._get_user_by_token(conn, token)
        return _room_wait(conn, room_id, user)


# ライブの開始
def room_start(room_id: int) -> None:
    with engine.begin() as conn:
        # 2人以上ルームにいないと開始できない
        # result = conn.execute(
        #     text("SELECT `user_id` FROM `room_member` WHERE `room_id` = :room_id"),
        #     {"room_id": room_id},
        # )

        # if len(result.all()) >= 2:
        conn.execute(
            text("UPDATE `room` SET `status`= :status WHERE `room_id`= :room_id"),
            {"status": WaitRoomStatus.LiveStart.value, "room_id": room_id},
        )


def get_end_time(conn, room_id: int) -> Optional[int]:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `end_time` FROM `room` WHERE `room_id`= :room_id"),
            {"room_id": room_id},
        )
        return result.one().end_time


# ライブの終了
def room_end(judge_count_list: list[int], score: int, token: str) -> None:
    with engine.begin() as conn:
        user = model._get_user_by_token(conn, token)
        conn.execute(
            text(
                "UPDATE `room_member` SET `score`= :score, `perfect`= :perfect, `great`= :great, "
                "`good`= :good, `bad`= :bad, `miss`= :miss WHERE `user_id`= :user_id"
            ),
            {
                "score": score,
                "perfect": judge_count_list[0],
                "great": judge_count_list[1],
                "good": judge_count_list[2],
                "bad": judge_count_list[3],
                "miss": judge_count_list[4],
                "user_id": user.id,
            },
        )

        result = conn.execute(
            text("SELECT `room_id` FROM `room_member` WHERE `user_id`= :user_id"),
            {"user_id": user.id},
        )
        room_id = result.one().room_id

        end_time = get_end_time(conn, room_id)

        if end_time is None:
            conn.execute(
                text(
                    "UPDATE `room` SET `end_time`= :end_time WHERE `room_id`= :room_id"
                ),
                {"end_time": int(time.time()), "room_id": room_id},
            )


# ルーム内のリザルトの取得
def _room_result(conn, room_id: int) -> Optional[list[ResultUser]]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `score`, `perfect`, `great`, `good`, `bad`, `miss`"
                "FROM `room_member` WHERE `room_id`= :room_id"
            ),
            {"room_id": room_id},
        )

        rows = result.all()

        if None in [row.score for row in rows]:
            # スコアが更新されない人がいた場合にスコア0で更新し、リザルトを表示させる。(一瞬モードではない想定)
            if time.time() - get_end_time(conn, room_id) >= 5:
                for row in rows:
                    if row.score is None:
                        conn.execute(
                            text(
                                "UPDATE `room_member` SET `score`= :score, `perfect`= :perfect, `great`= :great, "
                                "`good`= :good, `bad`= :bad, `miss`= :miss WHERE `user_id`= :user_id"
                            ),
                            {
                                "score": 0,
                                "perfect": 0,
                                "great": 0,
                                "good": 0,
                                "bad": 0,
                                "miss": 0,
                                "user_id": row.user_id,
                            },
                        )
            return []

        conn.execute(
            text("DELETE FROM `room` WHERE `room_id` = :room_id"), {"room_id": room_id}
        )
        # conn.execute(
        #     text("DELETE FROM `room_member` WHERE `room_id` = :room_id"),
        #     {"room_id": room_id},
        # )

        return [
            ResultUser(
                user_id=row.user_id,
                judge_count_list=[row.perfect, row.great, row.good, row.bad, row.miss],
                score=row.score,
            )
            for row in rows
        ]


def room_result(room_id: int) -> Optional[list[ResultUser]]:
    with engine.begin() as conn:
        return _room_result(conn, room_id)


def get_room_owner_id(conn, room_id: int) -> Optional[int]:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `owner_id` FROM `room` WHERE `room_id`= :room_id"),
            {"room_id": room_id},
        )

        return result.one().owner_id


def room_leave(room_id: int, token: str) -> None:
    with engine.begin() as conn:
        user = model._get_user_by_token(conn, token)

        conn.execute(
            text(
                "DELETE FROM `room_member` "
                "WHERE `room_id`= :room_id AND `user_id`= :user_id"
            ),
            {"room_id": room_id, "user_id": user.id},
        )

        if get_room_owner_id(conn, room_id) == user.id:
            result = conn.execute(
                text("SELECT `user_id` FROM `room_member` WHERE `room_id`= :room_id"),
                {"room_id": room_id},
            )
            try:
                rows = result.all()
                conn.execute(
                    text(
                        "UPDATE `room` SET `owner_id`= :owner_id WHERE `room_id`= :room_id"
                    ),
                    {"owner_id": rows[0].user_id, "room_id": room_id},
                )

            except:
                conn.execute(
                    text("DELETE FROM `room` WHERE `room_id` = :room_id"),
                    {"room_id": room_id},
                )


if __name__ == "__main__":
    conn = engine.connect()
    token_list = [model.create_user(name="ho", leader_card_id=1) for i in range(10)]
    model.update_user(token_list[0], "honoka", 50)
    user_list = [model._get_user_by_token(conn, token) for token in token_list]
    print("user:", user_list[0])

    room_id_list = [
        _create_room(
            conn,
            live_id=i,
            select_difficulty=LiveDifficulty.normal,
            user=user,
        )
        for i, user in enumerate(user_list)
    ]

    print("room_id:", room_id_list)

    room_list = get_room_list(1)
    print("roomlist(live_id=1):", room_list)

    room_list = get_room_list(0)
    print("roomlist(live_id=all):", room_list)

    for i in range(len(room_id_list)):
        if i % 2 == 0:
            room_start(room_id_list[i][0])
    room_list = get_room_list(0)
    print("roomlist(live_id=wait_room):", room_list)

    join_token = model.create_user(name="ho", leader_card_id=1)
    join_result = _room_join(
        conn,
        room_list[0].room_id,
        LiveDifficulty.normal,
        model._get_user_by_token(conn, join_token).id,
    )
    print("join_result:", join_result)

    room_owner_id = get_room_owner_id(conn, room_list[0].room_id)
    print("owner_id:", room_owner_id)

    room_leave(room_list[0].room_id, token_list[1])
    print("leave OK")

    result = _create_room(
        conn,
        live_id=i,
        select_difficulty=LiveDifficulty.normal,
        user=user_list[1],
    )
