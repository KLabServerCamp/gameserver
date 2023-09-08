import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text

from .db import engine

_MAX_ROOM_MEMBER = 4


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolusion = 3


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


# サーバーで生成するオブジェクトは strict を使う
class SafeUser(BaseModel, strict=True):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


class RoomInfo(BaseModel, strict=True):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class CreateRoomRequest(BaseModel, strict=True):
    live_id: int
    select_difficulty: int


class RoomUser(BaseModel, strict=True):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel, strict=True):
    user_id: int
    judge_count_list: list[int]
    score: int


# UUID4は天文学的な確率だけど衝突する確率があるので、気にするならリトライする必要がある。
# サーバーでリトライしない場合は、クライアントかユーザー（手動）にリトライさせることになる。
# ユーザーによるリトライは一般的には良くないけれども、確率が非常に低ければ許容できる場合もある。
def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id)"
                " VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        print(f"create_user(): {result.lastrowid=}")
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `token`, `leader_card_id`"
            "FROM `user` WHERE `token`=:token"
        ),
        {"token": token},
    )
    print(result)
    return result.fetchone()


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id "
                "WHERE token=:token"
            ),
            {"name": name, "leader_card_id": leader_card_id, "token": token},
        )
        print({"name": name, "leader_card_id": leader_card_id, "token": token})
        conn.commit()


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        result = conn.execute(
            text("INSERT INTO `rooms` (`live_id`)" "VALUES (:live_id)"),
            {"live_id": live_id},
        )
        room_id = result.lastrowid
        print("---room_id---")
        print(room_id)
        conn.execute(
            text(
                "INSERT INTO `room_member` "
                "(`room_id`, `user_id`, `difficulty`, `is_host`) "
                "VALUES(:room_id, :user_id, :difficulty, :is_host)"
            ),
            {
                "room_id": room_id, "user_id": user.id,
                "difficulty": int(difficulty), "is_host": True
            }
        )
        conn.commit()
        return room_id


def room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        req = conn.execute(text("SELECT `room_id`, `live_id` from `rooms`"))
        ret = req.fetchall()
        print(ret)
        room_ids = []
        live_ids = []
        for room_id, now_live_id in ret:
            print(str(room_id) + " : " + str(now_live_id))
            if now_live_id == live_id or live_id == 0:
                room_ids.append(room_id)
                live_ids.append(now_live_id)
        print("---room_ids---")
        print(room_ids)
        print("---live_ids---")
        print(live_ids)
        joined_user_count = []
        for id in room_ids:
            req = conn.execute(
                text(
                    "SELECT COUNT(1) FROM `room_member` WHERE room_id=:room_id"
                ),
                {"room_id": id},
            )
            joined_user_count.append(req.fetchall()[0][0])
        print(joined_user_count)
        ret_value = []
        for index, _ in enumerate(room_ids):
            row = RoomInfo(
                room_id=room_ids[index],
                live_id=live_ids[index],
                joined_user_count=joined_user_count[index],
                max_user_count=_MAX_ROOM_MEMBER
            )
            ret_value.append(row)
        print(ret_value)
        return ret_value


def _join_room(token: str, room_id: int,
               select_difficulty: LiveDifficulty) -> JoinRoomResult:
    with engine.begin() as conn:
        user = _get_user_by_token(conn=conn, token=token)
        print(user)
        req = conn.execute(
            text(
                "SELECT `room_state` FROM `rooms` WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
        state = req.fetchone()[0]
        print("--- room_state ---")
        print(state)
        if state == WaitRoomStatus.Dissolusion:
            return JoinRoomResult.Disbanded
        req = conn.execute(
            text(
                "SELECT COUNT(1) FROM `room_member` WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
        count = req.fetchone()[0]
        print(count)
        if count >= _MAX_ROOM_MEMBER:
            return JoinRoomResult.RoomFull
        else:
            conn.execute(
                text(
                    "INSERT INTO `room_member` (`room_id`, `user_id`, `difficulty`)"
                    "VALUES (:room_id, :user_id, :difficulty)"
                ),
                {
                    "room_id": room_id,
                    "user_id": user.id,
                    "difficulty": int(select_difficulty)
                }
            )
            conn.commit()
            return JoinRoomResult.Ok


def get_room_status(room_id: int) -> WaitRoomStatus:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `room_state` FROM `rooms` WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
        state = result.fetchone()[0]
        print("--- room_state ---")
        print(state)
        return state


def get_user_list(me: int, room_id: int) -> list[RoomUser]:
    with engine.begin() as conn:
        req = conn.execute(
            text(
                "SELECT `user_id`,`difficulty`,`is_host`"
                "FROM `room_member` WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
        user_ids = []
        difficulties = []
        is_hosts = []
        user_names = []
        user_leader_cards = []
        result = req.fetchall()
        for user_id, difficulty, is_host in result:
            user_ids.append(user_id)
            difficulties.append(difficulty)
            is_hosts.append(is_host)
            req = conn.execute(
                text(
                    "SELECT `name`, `leader_card_id` FROM `user` "
                    "WHERE id=:id;"
                ),
                {"id": user_id}
            )
            result = req.fetchall()[0]
            print("--- result ---")
            user_names.append(result[0])
            user_leader_cards.append(result[1])
        print("user_ids", end=" : ")
        print(user_ids)
        print("difficulties", end=" : ")
        print(difficulties)
        print("is_hosts", end=" : ")
        print(is_hosts)
        print("user_names", end=" : ")
        print(user_names)
        print("user_leader_cards", end=" : ")
        print(user_leader_cards)
        user_list = []
        for index, _ in enumerate(user_ids):
            user = RoomUser(
                user_id=user_ids[index],
                select_difficulty=LiveDifficulty(difficulties[index]),
                is_host=bool(is_hosts[index]),
                name=user_names[index],
                leader_card_id=user_leader_cards[index],
                is_me=bool(user_ids[index] == me)
            )
            user_list.append(user)
        return user


def is_host(user_id: int, room_id: int) -> bool:
    with engine.begin() as conn:
        req = conn.execute(
            text(
                "SELECT `is_host` FROM `room_member` "
                "WHERE room_id=:room_id "
                "AND user_id=:user_id"
            ),
            {"room_id": room_id, "user_id": user_id}
        )
        result = req.fetchone()[0]
        print("--- result ---")
        print(result)
        if (result):
            return True
        else:
            return False


def change_room_state(room_id: int, room_state: WaitRoomStatus) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `rooms` SET room_state=:room_state "
                "WHERE room_id=:room_id"
            ),
            {"room_state": int(room_state), "room_id": room_id}
        )
        conn.commit()


def save_score(user_id: int, room_id: int, score: int,
               judge_count_list: list[int]):
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `room_member` "
                "SET score=:score,"
                "perfect=:perfect, great=:great,"
                "good=:good, bad=:bad, miss=:miss "
                "WHERE user_id=:user_id "
                "AND room_id=:room_id"
            ),
            {
                "score": score, "perfect": judge_count_list[0],
                "great": judge_count_list[1],
                "good": judge_count_list[2],
                "bad": judge_count_list[3],
                "miss": judge_count_list[4],
                "user_id": user_id,
                "room_id": room_id
            }
        )
        conn.commit()


def everyone_end(room_id: int) -> bool:
    with engine.begin() as conn:
        req = conn.execute(
            text(
                "SELECT `score` FROM room_member "
                "WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
        result = req.fetchall()
        # print("--- result ---")
        # print(result)
        scores = []
        for score in result:
            scores.append(score[0])
        print("--- everyone ended? ---")
        if None in scores:
            print("false")
            return False
        else:
            print("true")
            return True


def get_result_user(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        req = conn.execute(
            text(
                "SELECT `user_id`, `score`, `perfect`, `great`,"
                "`good`, `bad`, `miss` FROM room_member "
                "WHERE room_id=:room_id"
            ),
            {"room_id": room_id}
        )
        result = req.fetchall()
        print(result)
        user_result_list = []
        for result_one in result:
            user_result = ResultUser(
                user_id=result_one[0],
                score=result_one[1],
                judge_count_list=[
                    result_one[2],
                    result_one[3],
                    result_one[4],
                    result_one[5],
                    result_one[6]
                ]
            )
            user_result_list.append(user_result)
        return user_result_list


def leave_room(user_id: int, room_id: int):
    with engine.begin() as conn:
        if is_host(user_id=user_id, room_id=room_id):
            change_room_state(room_id=room_id,
                              room_state=WaitRoomStatus.Dissolusion)
        conn.execute(
            text(
                "DELETE FROM `room_member` "
                "WHERE room_id=:room_id AND user_id=:user_id"
            ),
            {"room_id": room_id, "user_id": user_id}
        )
        conn.commit()
