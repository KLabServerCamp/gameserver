from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from ..db import engine
from .base import JoinRoomResult, LiveDifficulty, ResultUser, RoomUser, WaitRoomStatus
from .user_models import _get_user_by_token, validUser

MAX_USER = 4

# Models for room
def get_rooms(live_id: int = 0):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `live_id`=:live_id AND `status`=1 AND `joined_user_count`<`max_user_count`"
            ),
            dict(live_id=live_id),
        )
        return result


def get_all_rooms():
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `status`=1 AND `joined_user_count`<`max_user_count`"
            )
        )
        return result


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty) -> int:
    usr = validUser(token)
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

        # room_memberにオーナーを登録
        result = conn.execute(
            text(
                "INSERT INTO `room_member` (`room_id`, `user_id`, `select_difficulty`, `is_host`) VALUES (:room_id, :user_id, :select_difficulty, true)"
            ),
            dict(
                room_id=room_id,
                user_id=usr.id,
                select_difficulty=int(select_difficulty),
            ),
        )

        return room_id


def get_room_users(token: str, room_id: int) -> tuple[WaitRoomStatus, list[RoomUser]]:
    usr = validUser(token)
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

        # 結果を詰める
        res = []
        for m in result.all():
            tmp = RoomUser(
                user_id=m.user_id,
                name=m.name,
                leader_card_id=m.leader_card_id,
                select_difficulty=LiveDifficulty(m.select_difficulty),
                is_me=(m.user_id == usr.id),
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
                "SELECT `joined_user_count`, `max_user_count`, `status` FROM `room` WHERE `room_id`=:room_id FOR UPDATE"
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
                    "INSERT INTO `room_member` (`room_id`, `user_id`, `select_difficulty`, `is_host`) VALUES (:room_id, :user_id, :select_difficulty, false)"
                ),
                dict(
                    room_id=room_id,
                    user_id=usr.id,
                    select_difficulty=int(select_difficulty),
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


def end_room(token: str, room_id: int, score: int, judge_count_list: list[int]) -> None:
    usr = validUser(token)
    with engine.begin() as conn:
        # TODO: 終わったはずのroomにscoreを登録しようとしたら弾く
        # TODO: 存在しないレコードに対してUpdateをかけてもエラーにならないので，
        #       変化したレコードが0だった場合にエラーを吐くようにする
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id`=:room_id"),
            dict(room_id=room_id),
        )
        try:
            status = result.one().status
        except:
            raise HTTPException(status_code=404)

        if status != 2:
            raise HTTPException(status_code=403)

        result = conn.execute(
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
        if result.rowcount != 1:
            raise HTTPException(status_code=404)


def get_results(room_id: int) -> list[ResultUser]:
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
                "SELECT `is_host` FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id FOR UPDATE"
            ),
            dict(room_id=room_id, user_id=usr.id),
        )
        try:
            is_host = result.one().is_host
        except:
            raise HTTPException(status_code=404)

        result = conn.execute(
            text(
                "DELETE FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            dict(room_id=room_id, user_id=usr.id),
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=404)

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

            if is_host:
                result = conn.execute(
                    text(
                        "SELECT `user_id` FROM `room_member` WHERE `room_id`=:room_id"
                    ),
                    dict(room_id=room_id),
                )
                next_host = result.first()

                conn.execute(
                    text(
                        "UPDATE `room_member` SET `is_host`=true WHERE `room_id`=:room_id AND `user_id`=:user_id"
                    ),
                    dict(room_id=room_id, user_id=next_host.user_id),
                )
