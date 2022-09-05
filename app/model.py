import json
import uuid
from enum import Enum, IntEnum
from typing import Dict, Optional, List, Tuple

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

MAX_USER = 4

# Enums
class LiveDifficulty(IntEnum):
    normal = 1
    hard = 2


class WaitRoomStatus(IntEnum):
    waiting = 1
    liveStart = 2
    dissolution = 3


class JoinRoomResult(IntEnum):
    ok = 1
    roomFull = 2
    disbanded = 3
    otherError = 4


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


# Models for room
def get_rooms(live_id: int = 0):
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `status`=1 AND `joined_user_count`<`max_user_count`"
                )
            )
        else:
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `live_id`=:live_id AND `status`=1 AND `joined_user_count`<`max_user_count`"
                ),
                dict(live_id=live_id),
            )
        return result


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty) -> int:
    validUser(token)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, joined_user_count, max_user_count) VALUES (:live_id, 1, :max_user_count)"
            ),
            dict(live_id=live_id, max_user_count=MAX_USER),
        )
        try:
            room_id = result.lastrowid
        except:
            raise HTTPException(status_code=500)

        # この部屋を作成したユーザを特定
        result = conn.execute(
            text("SELECT `id` FROM `user` WHERE `token`=:token"), dict(token=token)
        )
        try:
            owner_id = result.one().id
        except:
            raise HTTPException(status_code=500)

        # room_memberにオーナーを登録
        result = conn.execute(
            text(
                "INSERT INTO `room_member` (`room_id`, `user_id`, `select_difficulty`, `is_host`) VALUES (:room_id, :user_id, :select_difficulty, :is_host)"
            ),
            dict(
                room_id=room_id,
                user_id=owner_id,
                select_difficulty=int(select_difficulty),
                is_host=True,
            ),
        )

        return room_id


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


def get_room_users(token: str, room_id: int) -> Tuple[WaitRoomStatus, list[RoomUser]]:
    validUser(token)
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id`=:room_id"),
            dict(room_id=room_id),
        )
        try:
            status = result.one().status
        except NoResultFound as e:
            raise HTTPException(status_code=404)

        result = conn.execute(
            text(
                "SELECT `user_id`, `name`, `leader_card_id`, `select_difficulty`, `is_host` FROM ( SELECT * FROM `room_member` WHERE `room_id`=:room_id) AS `rm` INNER JOIN `user` ON rm.user_id = user.id"
            ),
            dict(room_id=room_id),
        )

        # このAPIをコールしているユーザを特定
        usr = _get_user_by_token(conn, token)

        # 結果を詰める
        res = []
        for m in result.all():
            tmp = RoomUser(
                user_id=m.user_id,
                name=m.name,
                leader_card_id=m.leader_card_id,
                select_difficulty=LiveDifficulty(m.select_difficulty),
                is_me=True if m.user_id == usr.id else False,
                is_host=m.is_host,
            )
            res.append(tmp)

        return WaitRoomStatus(status), res


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    usr = validUser(token)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `joined_user_count`, `max_user_count`, `status` FROM `room` WHERE `room_id`=:room_id"
            ),
            dict(room_id=room_id),
        )
        try:
            room = result.one()
        except NoResultFound as e:
            return JoinRoomResult.otherError

        # 満員時
        if room.joined_user_count >= room.max_user_count:
            return JoinRoomResult.roomFull

        # 既に解散済み
        if room.status == WaitRoomStatus.dissolution:
            return JoinRoomResult.disbanded

        # memberにinsert
        try:
            conn.execute(
                text(
                    "INSERT INTO `room_member` (`room_id`, `user_id`, `select_difficulty`, `is_host`) VALUES (:room_id, :user_id, :select_difficulty, :is_host)"
                ),
                dict(
                    room_id=room_id,
                    user_id=usr.id,
                    select_difficulty=int(select_difficulty),
                    is_host=False,
                ),
            )

            # 参加人数を増やす
            conn.execute(
                text(
                    "UPDATE `room` SET `joined_user_count`=:count WHERE `room_id`=:room_id"
                ),
                dict(count=room.joined_user_count + 1, room_id=room_id),
            )
        except Exception as e:
            print(e)
            return JoinRoomResult.otherError

        return JoinRoomResult.ok


def start_room(token: str, room_id: int) -> None:
    usr = validUser(token)
    with engine.begin() as conn:
        # ホスト以外が開始しようとしたら却下
        result = conn.execute(
            text(
                "SELECT `user_id` FROM `room_member` WHERE `room_id`=:room_id AND `is_host`=true"
            ),
            dict(room_id=room_id),
        )
        try:
            if result.one().user_id != usr.id:
                return
        except NoResultFound as e:
            return

        conn.execute(
            text("UPDATE `room` SET `status`=:status WHERE `room_id`=:room_id"),
            dict(status=int(WaitRoomStatus.liveStart), room_id=room_id),
        )


def end_room(token: str, room_id: int, score: int, judge_count_list: List[int]) -> None:
    usr = validUser(token)
    with engine.begin() as conn:
        # TODO: 終わったはずのroomにscoreを登録しようとしたら弾く
        # TODO: 存在しないレコードに対してUpdateをかけてもエラーにならないので，
        #       変化したレコードが0だった場合にエラーを吐くようにする

        conn.execute(
            text(
                "UPDATE `room_member` SET `judge_count_list`=:judge_count_list, `score`=:score WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            dict(
                judge_count_list=",".join(map(str, judge_count_list)),
                score=score,
                room_id=room_id,
                user_id=usr.id,
            ),
        )


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: List[int]
    score: int


def get_results(room_id: int) -> List[ResultUser]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id` FROM `room_member` WHERE `room_id`=:room_id AND (`judge_count_list` IS NULL OR `score` IS NULL)"
            ),
            dict(room_id=room_id),
        )
        if len(result.all()) != 0:
            return []

        result = conn.execute(
            text(
                "SELECT `user_id`, `judge_count_list`, `score` FROM `room_member` WHERE `room_id`=:room_id"
            ),
            dict(room_id=room_id),
        )

        res = []
        try:
            for userRes in result.all():
                tmp = ResultUser(
                    user_id=userRes.user_id,
                    judge_count_list=[
                        int(i) for i in userRes.judge_count_list.split(",")
                    ],
                    score=userRes.score,
                )
                res.append(tmp)
        except Exception as e:
            print(e)
            return []

        result = conn.execute(
            text("UPDATE `room` SET `status`=3 WHERE `room_id`=:room_id"),
            dict(room_id=room_id),
        )

        return res


def leave_room(token: str, room_id: int):
    usr = validUser(token)
    # TODO: ホスト委譲も追加する
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `joined_user_count` FROM `room` WHERE `room_id`=:room_id FOR UPDATE"
            ),
            dict(room_id=room_id),
        )
        try:
            user_count = result.one().joined_user_count
        except:
            raise HTTPException(status_code=404)

        result = conn.execute(
            text(
                "DELETE FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            dict(room_id=room_id, user_id=usr.id),
        )
        print(result.rowcount)
        if result.rowcount != 1:
            raise HTTPException(status_code=404)

        print(user_count)
        print(user_count)
        print(user_count)
        print(user_count)
        if user_count == 1:
            conn.execute(
                text(
                    "UPDATE `room` SET `joined_user_count`=:count, `status`=3 WHERE `room_id`=:room_id"
                ),
                dict(count=user_count - 1, room_id=room_id),
            )
        else:
            conn.execute(
                text(
                    "UPDATE `room` SET `joined_user_count`=:count WHERE `room_id`=:room_id"
                ),
                dict(count=user_count - 1, room_id=room_id),
            )
