import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import MultipleResultsFound, NoResultFound

from .db import engine
from time import time

class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


# サーバーで生成するオブジェクトは strict を使う
class SafeUser(BaseModel, strict=True):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    # UUID4は天文学的な確率だけど衝突する確率があるので、気にするならリトライする必要がある。
    # サーバーでリトライしない場合は、クライアントかユーザー（手動）にリトライさせることになる。
    # ユーザーによるリトライは一般的には良くないけれども、確率が非常に低ければ許容できる場合もある。
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id)"
                " VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        print(f"create_user(): {result.lastrowid=}") # DB側で生成されたPRIMARY KEYを参照できる
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    res = conn.execute(
        text("SELECT * FROM `user` WHERE `token`=:token"), {"token": token}
    )
    try:
        row = res.one()
        print(row.id)
    except (NoResultFound, MultipleResultsFound):
        return None
    return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id WHERE `token`=:token"""
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    """入場結果"""

    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    """部屋の待ち状態"""

    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class DBResponseError(IntEnum):
    """エラーの種類"""

    NoResultFound = 1
    MultipleResultsFound = 2
    OtherError = 3


def get_room(conn, room_id: int):
    """部屋を取得する(live_id以外)"""
    res = conn.execute(text(
        "SELECT `joined_user_count`, `max_user_count` FROM `room` WHERE `room_id`=:room_id"
    ), {
        "room_id": room_id
    })
    try:
        row = res.one()
        return row
    except NoResultFound:
        return DBResponseError.NoResultFound
    except MultipleResultsFound:
        return DBResponseError.MultipleResultsFound


def get_room_members(conn, room_id: int):
    """部屋のユーザ情報を取ってくる"""
    res = conn.execute(text(
        "SELECT `member_list` FROM `room_member` WHERE `room_id`=:room_id"
    ), {
        "room_id": room_id
    })
    try:
        row = res.one()
        return row
    except NoResultFound:
        return DBResponseError.NoResultFound
    except MultipleResultsFound:
        return DBResponseError.MultipleResultsFound


def get_room_user(conn, user_id: int):
    """ユーザの部屋での情報を取得"""
    res = conn.execute(text(
        "SELECT `select_difficulty`, `score`, `judge_count_list` FROM `room_user` WHERE `user_id`=:user_id"
    ), {
        "user_id": user_id
    })
    try:
        row = res.one()
        return row
    except (NoResultFound, MultipleResultsFound):
        return DBResponseError.OtherError


def get_room_lived(conn, room_id: int):
    """部屋のライブ状態を取ってくる"""
    res = conn.execute(text(
        "SELECT `lived` FROM `room` WHERE `room_id`=:room_id"
    ), {
        "room_id": room_id
    })
    try:
        row = res.one()
        return row
    except (NoResultFound, MultipleResultsFound):
        return DBResponseError.OtherError
    

def get_user(conn, user_id: int):
    """部屋のライブ状態を取ってくる"""
    res = conn.execute(text(
        "SELECT `name`, `leader_card_id` FROM `user` WHERE `id`=:user_id"
    ), {
        "user_id": user_id
    })
    try:
        row = res.one()
        return row
    except (NoResultFound, MultipleResultsFound):
        return DBResponseError.OtherError


def update_room_count(conn, room_id: int, count: int) -> None:
    """部屋のjoined_user_countを更新する"""
    conn.execute(text(
        "UPDATE `room` SET `joined_user_count`=:count WHERE `room_id`=:room_id"
    ), {
        "count": count,
        "room_id": room_id
    })


def insert_room_user(conn, user_id: int, room_id: int, select_difficulty: LiveDifficulty):
    """部屋のuser情報を設定する"""
    conn.execute(text(
        "INSERT INTO `room_user` (`user_id`, `room_id`, `select_difficulty`) VALUES(:user_id, :room_id, :select_difficulty)"
    ), {
        "user_id": user_id,
        "room_id": room_id,
        "select_difficulty": int(select_difficulty)
    })


def delete_room_user(conn, user_id):
    """部屋のuser情報を削除する"""
    conn.execute(text(
        "DELETE FROM `room_user` WHERE `user_id`=:user_id"
        ), {
            "user_id": user_id
        })


def check_room_status(room) -> JoinRoomResult:
    if room == DBResponseError.NoResultFound:
        return JoinRoomResult.Disbanded
    if room == DBResponseError.MultipleResultsFound:
        return JoinRoomResult.OtherError
    if room.joined_user_count < room.max_user_count:
        return JoinRoomResult.Ok
    else:
        return JoinRoomResult.RoomFull


def insert_room_member(conn, room_id: int, user_id: int):
    member_list = str(user_id)
    """room_memberに新規に作った部屋情報を加える"""
    conn.execute(text(
            "INSERT INTO `room_member` (`room_id`, `member_list`) VALUES(:room_id, :member_list)"
        ), {
            "room_id": room_id,
            "member_list": member_list
        })


def update_room_member(conn, room_id, member_list: str):
    conn.execute(text(
            "UPDATE `room_member` SET `member_list`=:member_list WHERE `room_id`=:room_id"
        ), {
            "member_list": member_list,
            "room_id": room_id
        })


def room_start_live(conn, room_id):
    conn.execute(text(
            "UPDATE `room` SET `lived`=true WHERE `room_id`=:room_id"
        ), {
            "room_id": room_id
        })


def delete_room(conn, room_id):
    conn.execute(text(
        "DELETE FROM `room` WHERE `room_id`=:room_id"
    ), {
        "room_id": room_id
    })


def delete_room_member(conn, room_id):
    conn.execute(text(
        "DELETE FROM `room_member` WHERE `room_id`=:room_id"
    ), {
        "room_id": room_id
    })


def get_room_users(conn, room_id):
    res = conn.execute(text(
        "SELECT `user_id`, `score`, `judge_count_list` FROM `room_user` WHERE `room_id`=:room_id"
    ), {
        "room_id": room_id
    })
    return res.all()


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        delete_room_user(conn, user.id)
        res = conn.execute(text(
            "INSERT INTO `room` (`live_id`) VALUES(:live_id)"
        ), {
            "live_id": live_id
        })
        insert_room_member(conn, res.lastrowid, user.id)
        insert_room_user(conn, user.id, res.lastrowid, select_difficulty)
    return res.lastrowid


def list_room(live_id: int):
    """部屋情報の配列を返す"""
    with engine.begin() as conn:
        if live_id == 0:
            res = conn.execute(text(
                "SELECT `room_id`, `joined_user_count`, `max_user_count`, `live_id` FROM `room` WHERE `lived`=false"
            ), {})
        else:
            res = conn.execute(text(
                "SELECT `room_id`, `joined_user_count`, `max_user_count`, `live_id` FROM `room` WHERE `live_id`=:live_id AND `lived`=false"
            ), {
                "live_id": live_id
            })
        try:
            rows = res.all()
        except NoResultFound:
            return None
        return rows


def join_room(token: str, room_id: int, select_difficulty: LiveDifficulty):
    """部屋に参加する"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        delete_room_user(conn, user.id)
        room = get_room(conn, room_id)
        room_status = check_room_status(room)
        if room_status != JoinRoomResult.Ok:
            return room_status
        room_members = get_room_members(conn, room_id)
        if room_members in (DBResponseError.NoResultFound, DBResponseError.MultipleResultsFound):
            return JoinRoomResult.OtherError
        room_members = room_members.member_list.split(',')
        if room_members[0] == '':
            room_members = []
        room_members.append(str(user.id))
        room_members = ",".join(room_members)
        update_room_member(conn, room_id, room_members)
        insert_room_user(conn, user.id, room_id, select_difficulty)
        update_room_count(conn, room_id, room.joined_user_count + 1)
        return JoinRoomResult.Ok
    

def wait_room(token: str, room_id: int):
    """部屋の待機情報を得る"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room = get_room(conn, room_id)
        room_status = check_room_status(room)
        room_members = get_room_members(conn, room_id)
        room_members = room_members.member_list.split(',')
        if room_members[0] == '':
            room_members = []
        room_members = list(map(lambda member: int(member), room_members))
        room_compiled_members = []
        for member_id in room_members:
            room_member = get_room_user(conn, member_id)
            member_info = get_user(conn, member_id)
            if room_member == DBResponseError.OtherError or member_info == DBResponseError.OtherError:
                return WaitRoomStatus.Dissolution, []
            room_member = {
                "user_id": member_id,
                "name": member_info.name,
                "leader_card_id": member_info.leader_card_id,
                "select_difficulty": room_member.select_difficulty,
                "is_me": (user.id == member_id),
                "is_host": (room_members[0] == member_id)
            }
            room_compiled_members.append(room_member)
        if room_status in (JoinRoomResult.Ok, JoinRoomResult.RoomFull):
            lived_status = get_room_lived(conn, room_id)
            if lived_status == DBResponseError.OtherError:
                return WaitRoomStatus.Dissolution, []
            if lived_status.lived:
                return WaitRoomStatus.LiveStart, room_compiled_members
            else:
                return WaitRoomStatus.Waiting, room_compiled_members
        else:
            return WaitRoomStatus.Dissolution, []


def start_room(token: str, room_id: int):
    """部屋のライブを開始する"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room_members = get_room_members(conn, room_id)
        room_members = room_members.member_list.split(',')
        if room_members[0] == '':
            room_members = []
        room_members = list(map(lambda member: int(member), room_members))
        if room_members[0] == user.id:
            room_start_live(conn, room_id)


def leave_room(token: str, room_id: int):
    """部屋から退出する"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room = get_room(conn, room_id)
        room_members = get_room_members(conn, room_id)
        room_members = room_members.member_list.split(',')
        if room_members[0] == '':
            room_members = []
        room_members = list(filter(lambda member: int(member)!=user.id, room_members))
        room_members = ",".join(room_members)
        update_room_member(conn, room_id, room_members)
        delete_room_user(conn, user.id)
        update_room_count(conn, room_id, room.joined_user_count - 1)


def end_room(token: str, room_id: int, judge_count_list: list[int], score: int):
    """ライブを終える"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        judge_count_list = list(map(lambda judge_count: str(judge_count), judge_count_list))
        conn.execute(text(
            "UPDATE `room_user` SET `score`=:score, `judge_count_list`=:judge_count_list WHERE `user_id`=:user_id AND `room_id`=:room_id"
        ), {
            "score": score,
            "judge_count_list": str(",".join(judge_count_list)),
            "user_id": user.id,
            "room_id": room_id
        })


def result_room(token: str, room_id: int):
    """ライブの結果"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        delete_room(conn, room_id)
        room_users = get_room_users(conn, room_id)
        room_compiled_users = []
        now, first_end = updateTime(conn, room_id)
        for room_user in room_users:
            if room_user.judge_count_list is None:
                if now - first_end > 60 * 1:
                    continue
                else:
                    return []
            judge_count_list = room_user.judge_count_list.split(',')
            judge_count_list = list(map(lambda judge_count: int(judge_count), judge_count_list))
            room_member = {
                "user_id": room_user.user_id,
                "judge_count_list": judge_count_list,
                "score": room_user.score
            }
            room_compiled_users.append(room_member)
        delete_room_member(conn, room_id)
        return room_compiled_users


def updateTime(conn, room_id):
    now = int(time())
    res = conn.execute(text(
        "SELECT `first_end` FROM `room_member` WHERE `room_id`=:room_id"
    ), {
        "room_id": room_id
    })
    try:
        row = res.one()
    except (MultipleResultsFound, NoResultFound):
        return now, now - 60 * 1
    if row.first_end is None:
        conn.execute(text(
            "UPDATE `room_member` SET `first_end`=:first_end WHERE `room_id`=:room_id"
        ), {
            "first_end": str(now),
            "room_id": room_id
        })
        first_end = now
    else:
        first_end = int(row.first_end)
    return now, first_end
    