import uuid
from enum import IntEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


# サーバーで生成するオブジェクトは strict を使う
class SafeUser(BaseModel, strict=True):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


class SafeRoom(BaseModel, strict=True):
    room_id: int
    owner_id: int
    live_id: int
    max_user_count: int
    status: int


class SafeRoomMember(BaseModel, strict=True):
    room_id: int
    user_id: int
    difficulty: int


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
        print(f"create_user(): {result.lastrowid=}")  # DB側で生成されたPRIMARY KEYを参照できる
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    res = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    row = res.one_or_none()
    if row is None:
        return None
    return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id WHERE `token`=:token"
            ),
            {"token": token, "name": name, "leader_card_id": leader_card_id},
        )


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        res = conn.execute(
            text("INSERT INTO `room` SET `owner_id`=:owner_id, `live_id`=:live_id"),
            {"owner_id": user.id, "live_id": live_id},
        )
        room_id = res.lastrowid
        res = conn.execute(
            text(
                "INSERT INTO `room_member` SET `room_id`=:room_id, `user_id`=:user_id, `difficulty`=:difficulty"
            ),
            {"room_id": room_id, "user_id": user.id, "difficulty": int(difficulty)},
        )
    return room_id


class RoomInfo(BaseModel, strict=True):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = 4


def _get_room_users_from_room_id(conn, room_id: int) -> list:
    """room_id のルームに join しているプレイヤーを返す"""
    res = conn.execute(
        text("SELECT `user_id` FROM `room_member` WHERE `room_id`=:room_id"),
        {"room_id": room_id},
    )
    return res.all()


def get_room_list(live_id: int) -> list:
    """
    live_id が一致する room を返す
    live_id が 0 ならば全ての room を返す
    """
    with engine.begin() as conn:
        if live_id == 0:
            res = conn.execute(text("SELECT `room_id`, `live_id` FROM `room`"))
        else:
            res = conn.execute(
                text(
                    "SELECT `room_id`, `live_id` FROM `room` WHERE `live_id`=:live_id"
                ),
                {"live_id": live_id},
            )
        rooms = []
        for room in res:
            rooms.append(
                RoomInfo(
                    room_id=room.room_id,
                    live_id=room.live_id,
                    joined_user_count=len(
                        _get_room_users_from_room_id(conn, room.room_id)
                    ),
                )
            )
        return rooms


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


def _get_room_from_room_id(conn, room_id: int) -> SafeRoom | None:
    res = conn.execute(
        text(
            "SELECT `room_id`, `owner_id`, `live_id`, `max_user_count`, `status` FROM `room` WHERE `room_id`=:room_id"
        ),
        {"room_id": room_id},
    )
    room = res.one_or_none()
    if room is None:
        return None
    return SafeRoom.model_validate(room, from_attributes=True)


def join_room(token: str, room_id: int, difficulty: LiveDifficulty) -> JoinRoomResult:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        # room_id の存在判定
        room = _get_room_from_room_id(conn, room_id)
        if room is None:
            return JoinRoomResult.Disbanded

        # room の人数が max に達している
        if len(_get_room_users_from_room_id(conn, room_id)) >= room.max_user_count:
            return JoinRoomResult.RoomFull

        # joinする
        res = conn.execute(
            text(
                "INSERT INTO `room_member` SET `room_id`=:room_id, `user_id`=:user_id, `difficulty`=:difficulty"
            ),
            {"room_id": room_id, "user_id": user.id, "difficulty": int(difficulty)},
        )
        return JoinRoomResult.Ok


class RoomUser(BaseModel, strict=True):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


def wait_room(token: str, room_id: int):
    # room_id から参加者を特定
    # それぞれの参加者について情報を取得し、 RoomUser のインスタンスを作る
    with engine.begin() as conn:
        req_user = _get_user_by_token(conn, token)
        if req_user is None:
            raise InvalidToken
        room_user_list: list[RoomUser] = []
        res = conn.execute(
            text(
                "SELECT `room_id`, `user_id`, `difficulty` FROM `room_member` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )

        room = _get_room_from_room_id(conn, room_id)
        if room is None:
            raise Exception

        for user_in_room in res:
            user = conn.execute(
                text(
                    "SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `id`=:user_id"
                ),
                {"user_id": user_in_room.user_id},
            ).one_or_none()
            if user is None:
                continue
            room_user_list.append(
                RoomUser(
                    user_id=user.id,
                    name=user.name,
                    leader_card_id=user.leader_card_id,
                    select_difficulty=LiveDifficulty(user_in_room.difficulty),
                    is_me=(user.id == req_user.id),
                    is_host=(user.id == room.owner_id),
                )
            )
        return room.status, room_user_list


def start_room(token: str, room_id: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room = _get_room_from_room_id(conn, room_id)
        if room is None:
            raise Exception
        if user.id != room.owner_id:
            raise Exception
        conn.execute(
            text("UPDATE `room` SET `status`=2 WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )


class LiveJudge(BaseModel):
    perfect: int
    great: int
    good: int
    bad: int
    miss: int


class ResultUser(BaseModel):
    user_id: int
    score: int
    judge_count_list: list[int]


def end_room(token: str, room_id: int, score: int, judge_count_list: list[int]):
    # room_member_result テーブルに全部突っ込む
    if len(judge_count_list) != 5:
        raise Exception
    # TODO: どうにかする
    user_judge = LiveJudge(
        perfect=judge_count_list[0],
        great=judge_count_list[1],
        good=judge_count_list[2],
        bad=judge_count_list[3],
        miss=judge_count_list[4],
    )
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room = _get_room_from_room_id(conn, room_id)
        if room is None:
            raise Exception
        conn.execute(
            text(
                """
                INSERT INTO `room_member_result` SET
                    `room_id`=:room_id,
                    `user_id`=:user_id,
                    `score`=:score,
                    `perfect`=:perfect,
                    `great`=:great,
                    `good`=:good,
                    `bad`=:bad,
                    `miss`=:miss
                """
            ),
            {
                "room_id": room_id,
                "user_id": user.id,
                "score": score,
                "perfect": user_judge.perfect,
                "great": user_judge.great,
                "good": user_judge.good,
                "bad": user_judge.bad,
                "miss": user_judge.miss,
            },
        )


def room_result(room_id: int):
    # TODO: タイムアウト処理
    with engine.begin() as conn:
        cnt = conn.execute(
            text(
                "SELECT COUNT(1) = (SELECT COUNT(1) FROM `room_member` WHERE `room_id`=:room_id) AS `is_full` FROM `room_member_result` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        ).one_or_none()
        if not cnt.is_full:
            return []
        res = conn.execute(
            text("SELECT * FROM `room_member_result` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        user_results = []
        for result in res:
            user_results.append(
                ResultUser(
                    user_id=result.user_id,
                    score=result.score,
                    judge_count_list=[
                        result.perfect,
                        result.great,
                        result.good,
                        result.bad,
                        result.miss,
                    ],
                )
            )
        return user_results


def _delete_user_from_room(conn, room_id: int, user_id: int) -> None:
    conn.execute(
        text(
            "DELETE FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
        ),
        {"room_id": room_id, "user_id": user_id},
    )


def _delete_room(conn, room_id) -> None:
    # room.status を 3 に変更
    conn.execute(
        text("UPDATE `room` SET `status`=3 WHERE `room_id`=:room_id"),
        {"room_id": room_id},
    )


def _change_room_owner(
    conn, room_id: int, owner: SafeUser, users_in_room: list
) -> None:
    # オーナーではない適当なユーザ 1 人にだけ owner 権限を移譲する
    for user in users_in_room:
        if user.user_id == owner.id:
            continue
        conn.execute(
            text("UPDATE `room` SET `owner_id`=:new_user_id WHERE `room_id`=:room_id"),
            {"new_user_id": user.user_id, "room_id": room_id},
        )
        break


def leave_room(token: str, room_id: int) -> None:
    # 退出ボタンを押したときに呼ばれる
    # room に 1 人しかいなければ部屋を潰す（このとき残っているのは必ず owner のはずである）
    # 複数人残っている && owner が抜けるときは owner 権限を他の member に移譲する
    # TODO: なんとかする
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room = _get_room_from_room_id(conn, room_id)
        if room is None:
            raise Exception

        users_in_room = _get_room_users_from_room_id(conn, room_id)

        # オーナーが抜ける場合、 room.owner_id を変更
        if user.id == room.owner_id:
            _change_room_owner(conn, room_id, user, users_in_room)

        _delete_user_from_room(conn, room_id, user.id)

        # 元から 1 人以下だった場合
        if len(users_in_room) <= 1:
            _delete_room(conn, room_id)
