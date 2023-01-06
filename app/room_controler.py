from enum import Enum
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

import random as rand


class LiveDifficulty(Enum):
    normal = 1
    hard = 2


class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(Enum):
    Waiting = 1
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

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


# NOTE:SafeRoomは閲覧可能なRoomの構成要素
class SafeRoom(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

    class Config:
        orm_mode = True


def _get_user_by_token(token: str):
    # NOTE: tokenからユーザー情報をもらう
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        return result.one()


def _room_close(room_id: int):
    # NOTE: room内部に一人もいなかった場合削除。
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `joined_user_count` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        if result.fetchone()[0] < 1:
            _ = conn.execute(
                text("DELETE FROM `room` WHERE `room_id`=:room_id"),
                {"room_id": room_id},
            )


def create_room(live_id: int, difficulty: LiveDifficulty, token: str):
    with engine.begin() as conn:
        # NOTE: 必要情報の設定。
        room_id = rand.getrandbits(10)
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        try:
            row = result.one()
        except NoResultFound:
            row = [0]
        player_id = row[0]
        _ = conn.execute(
            text("INSERT INTO `room` (`live_id`,`room_id`) VALUES (:live_id, :room_id)"),
            {"live_id": live_id, "room_id": room_id},
        )
        result = conn.execute(
            text("INSERT INTO `room_member` (`room_id`,  `owner`, `player_id`, `select_difficulty`) VALUE(:room_id, :player_id, :player_id, :select_difficulty)"),
            {"room_id": room_id, "player_id": player_id, "select_difficulty": difficulty.value},
        )
        print(result)
        return room_id


def room_list(live_id: int, token: str):
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text("SELECT `room_id`,`live_id`,`joined_user_count`,`max_user_count` FROM `room` WHERE `status`=1"),
                {"live_id": live_id},
            )
        else:
            result = conn.execute(
                text("SELECT `room_id`,`live_id`,`joined_user_count`,`max_user_count` FROM `room` WHERE `live_id`=:live_id AND `status`=1"),
                {"live_id": live_id},
            )
        rows = result.fetchall()
        rooms = [SafeRoom.from_orm(r) for r in rows]
        return rooms


def room_join(room_id: int, difficulty: LiveDifficulty, token: str) -> JoinRoomResult:
    with engine.begin() as conn:
        user = _get_user_by_token(token=token)
        player_id = user[0]
        result = conn.execute(
            text("SELECT `joined_user_count`,`max_user_count` FROM `room` WHERE `room_id`=:room_id FOR UPDATE"),
            {"room_id": room_id}
        )
        try:
            row = result.one()
        except NoResultFound:
            _ = conn.execute(text("COMMIT"))
            return JoinRoomResult.Disbanded
        if row[0] < row[1]:
            _ = conn.execute(
                text("INSERT INTO `room_member` (`room_id`, `player_id`, `select_difficulty`) VALUE(:room_id, :player_id, :select_difficulty)"),
                {"room_id": room_id, "player_id": player_id, "select_difficulty": difficulty.value},
            )
        else:
            _ = conn.execute(text("COMMIT"))
            return JoinRoomResult.RoomFull
        # NOTE:Room内の人数を数え上げ、それで人数の更新をする。
        result = conn.execute(
            text("SELECT `owner`,`player_id` FROM `room_member` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        ) 
        rows = result.fetchall()
        _ = conn.execute(
            text("UPDATE `room` SET `joined_user_count`=:num WHERE `room_id`=:room_id"),
            {"num": len(rows), "room_id": room_id},
        )
        _ = conn.execute(text("COMMIT"))
        return JoinRoomResult.Ok


def _room_member_list(room_id: int, user_id: int):
    members = []
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `player_id`, `select_difficulty`, `owner` FROM `room_member` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        row = result.fetchall()
        for player in row:
            data = conn.execute(
                text("SELECT `name`, `leader_card_id` FROM `user` WHERE `id`=:player_id"),
                {"player_id": player[0]}
            )
            try:
                data_row = data.one()
            except NoResultFound:
                continue
            members.append(RoomUser(user_id=player[0],
                                    name=data_row[0],
                                    leader_card_id=data_row[1],
                                    select_difficulty=player[1],
                                    is_host=True if player[0] == player[2] else False,
                                    is_me=True if player[0] == user_id else False))
    return members


def room_wait(room_id: int, token: str):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        user_id = result.one()[0]
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        try:
            row = result.one()
        except NoResultFound:
            return WaitRoomStatus.Dissolution, []
        if row[0] == 1:
            return WaitRoomStatus.Waiting, _room_member_list(room_id=room_id, user_id=user_id)
        else:
            return WaitRoomStatus.LiveStart, _room_member_list(room_id=room_id, user_id=user_id)


def room_start(room_id: int, token: str):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        user = result.one()[0]
        result = conn.execute(
            text("SELECT `room_id` FROM `room_member` WHERE `room_id`=:room_id AND `owner`=:user_id"),
            {"room_id": room_id, "user_id": user},
        )
        if result is not None:
            _ = conn.execute(
                text("UPDATE `room` SET `status`=:status WHERE `room_id`=:room_id"),
                {"status": 2, "room_id": room_id},
            )
    pass


def room_end(room_id: int, judge_count_list: list[int], score: int, token: str):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"),
            {"token": token},
        )
        user = result.one()[0]
        _ = conn.execute(
            text("UPDATE `room_member` "
                 "SET `judge_count_perfect`=:perfect,"
                 " `judge_count_great`=:great,"
                 " `judge_count_good`=:good,"
                 " `judge_count_bad`=:bad,"
                 " `judge_count_miss`=:miss,"
                 " `player_score`=:score,"
                 " `done`= 1"
                 " WHERE `room_id`=:room_id AND `player_id`=:user_id"),
            {"perfect": judge_count_list[0],
             "great": judge_count_list[1],
             "good": judge_count_list[2],
             "bad": judge_count_list[3],
             "miss": judge_count_list[4],
             "score": score,
             "room_id": room_id,
             "user_id": user},
        )
    pass


def room_result(room_id: int):
    results = []
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM `room_member` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
            )
        row = result.fetchall()
        for d in row:
            if d[-1] == 0:
                return []
            results.append(ResultUser(user_id=d[3],
                                      judge_count_list=[d[5], d[6], d[7], d[8], d[9]],
                                      score=d[-2]))
        return results


def room_leave(room_id: int, token: str):
    # NOTE:必要なもの（誰もいなくなったらroomを削除する。ownerが抜けたら別の人をownerにする）
    user = _get_user_by_token(token=token)
    with engine.begin() as conn:
        _ = conn.execute(
            text("DELETE FROM `room_member` WHERE `room_id`=:room_id AND `player_id`=:user_id"),
            {"room_id": room_id, "user_id": user[0]},
        )
        _ = conn.execute(
            text("UPDATE `room` SET `joined_user_count`=`joined_user_count`-1 WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        _room_close(room_id=room_id)
    pass