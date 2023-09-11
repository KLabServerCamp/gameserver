import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""
    print("create_room() error")


class InvalidError(Exception):
    print("Invalid error")


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
        print(f"create_user(): {result.lastrowid=}")  # DB側で生成されたPRIMARY KEYを参照できる
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    result = conn.execute(
        text("SELECT id, name, leader_card_id FROM `user` WHERE token=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE token=:token"
            ),
            {"name": name, "leader_card_id": leader_card_id, "token": token},
        )


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""
    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    """参加判定"""
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    """ルーム状態"""
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel, strict=True):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = 4


def room_create(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, room_master, joined_user_count, status)"
                " VALUES (:live_id, :room_master, :joined_user_count, :status)"
            ),
            {"live_id": live_id, "room_master": user.id, "joined_user_count": 0, "status": 1},
        )
        room_id = result.lastrowid
        print(f"create room, room id: {room_id}")
        insert_room_member(conn, room_id, user.id, difficulty, 1)
        up_joined_count(conn, room_id)
        print(f"create room: {room_id}")
        conn.commit()
        return room_id


def room_list(live_id: int):
    """楽曲IDから空き部屋を探す"""
    with engine.begin() as conn:
        print(f"live_id: {live_id}")
        result = conn.execute(
            text(
                """
                SELECT `id`, `live_id`, `joined_user_count` FROM `room` WHERE live_id=:live_id AND joined_user_count BETWEEN 1 AND 3 AND status = 1
                """
            ),
            {"live_id": live_id},
        )
        room_list: list[RoomInfo] = []
        row = result.all()
        if len(row) == 0:
            conn.commit()
            return room_list

        for res in row:
            room_list.append(
                RoomInfo(
                    room_id=res.id,
                    live_id=res.live_id,
                    joined_user_count=res.joined_user_count,
                    max_user_count=4,
                )
            )
        print(f"room list search: {room_list}")
        conn.commit()
        return room_list


def room_join(token: str, room_id: int, difficulty: LiveDifficulty):
    """入室処理"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        judge_join = get_upto_member_room(room_id)
        if judge_join == JoinRoomResult.Ok:
            print("try join")
            result = conn.execute(
                text(
                    """
                    SELECT in_order FROM `room_member` WHERE room_id=:room_id ORDER BY in_order DESC LIMIT 1
                    """
                ),
                {"room_id": room_id},
            ).one()
            if result is None:
                return JoinRoomResult.OtherError
            user_order = result[0]
            print(f"recent order in room {user_order}")
            insert_room_member(conn, room_id, user.id, difficulty, user_order + 1)
            up_joined_count(conn, room_id)
        conn.commit()
        return judge_join


def get_room_user_count(conn, room_id: int):
    print("get room user count")
    result = conn.execute(
        text(
            "SELECT joined_user_count FROM `room` WHERE id=:room_id"
        ),
        {"room_id": room_id},
    ).one()
    res = result[0]
    print(res)
    if res is None:
        return None
    return res


def get_upto_member_room(room_id: int):
    print("get upto member room")
    with engine.begin() as conn:
        res = conn.execute(
            text(
                "SELECT joined_user_count FROM `room` WHERE id=:room_id"
            ),
            {"room_id": room_id},
        ).one()
        result = res[0]
        print(f"now joined user count: {result}")
        if result > 4:
            return JoinRoomResult.OtherError
        elif result == 4:
            return JoinRoomResult.RoomFull
        elif result >= 0:
            return JoinRoomResult.Ok
        elif result < 0:
            return JoinRoomResult.Disbanded
        return JoinRoomResult.OtherError


def insert_room_member(conn, room_id: int, user_id: int, difficulty: LiveDifficulty, user_count: int):
    print("room member table join")
    conn.execute(
        text(
            """
            INSERT INTO `room_member` (room_id, user_id, difficulty, in_order, score, perfect, great, good, bad, miss)
             VALUES (:room_id, :user_id, :difficulty, :in_order, :score, :perfect, :great, :good, :bad, :miss)
            """
        ),
        {"room_id": room_id, "user_id": user_id, "difficulty": int(difficulty), "in_order": user_count, "score": -1, "perfect": 0, "great": 0, "good": 0, "bad": 0, "miss": 0},
    )


def up_joined_count(conn, room_id: int):
    print("up user count")
    conn.execute(
        text(
            """
            UPDATE `room` SET joined_user_count = joined_user_count + 1 WHERE id=:room_id
            """
        ),
        {"room_id": room_id},
    )


def down_joined_count(conn, room_id: int):
    print("down user count")
    conn.execute(
        text(
            """
            UPDATE `room` SET joined_user_count = joined_user_count - 1 WHERE id=:room_id
            """
        ),
        {"room_id": room_id},
    )


def get_room_status(conn, room_id: int):
    print("get room status")
    result = conn.execute(
        text(
            """
            SELECT `status` FROM `room` WHERE id=:room_id
            """
        ),
        {"room_id": room_id},
    ).one()
    if result is None:
        return None
    res = result[0]
    print(f"room status: {res}")
    return WaitRoomStatus(res)


def update_room_status(conn, room_id: int, status: WaitRoomStatus):
    print(f"update room status {status}")
    conn.execute(
        text(
            "UPDATE `room` SET status=:status WHERE id=:room_id"
        ),
        {"status": int(status), "room_id": room_id},
    )


class WaitUserInfo(BaseModel, strict=True):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_host: bool


def room_wait(token: str, room_id: int):
    with engine.begin() as conn:
        status = get_room_status(conn, room_id)
        if status is None:
            raise InvalidError(Exception)

        host = get_room_host(conn, room_id)

        result = conn.execute(
            text(
                """
                SELECT user.id, user.name, user.leader_card_id, room_member.difficulty
                FROM user JOIN room_member ON user.id = room_member.user_id WHERE room_member.room_id = :room_id
                """
            ),
            {"room_id": room_id},
        )

        res = result.fetchall()
        print(f"get room id from user by room id from room member {res}")
        user_info: list[WaitUserInfo] = []
        for users in res:
            print(users.id)
            print(users.name)
            print(users.leader_card_id)
            print(users.difficulty)
            if host == users.id:
                is_host = True
                print("True")
            else:
                is_host = False
                print("False")
            user_info.append(
                WaitUserInfo(
                    user_id=users.id,
                    name=users.name,
                    leader_card_id=users.leader_card_id,
                    select_difficulty=LiveDifficulty(users.difficulty),
                    is_host=is_host,
                )
            )
        conn.commit()
        return status, user_info


def get_room_host(conn, room_id: int):
    print("get room host")
    result = conn.execute(
        text(
            """
            SELECT `room_master` FROM `room` WHERE id=:room_id
            """
        ),
        {"room_id": room_id},
    ).one_or_none()
    if result is None:
        raise InvalidError(Exception)
    res = result[0]
    print(f"room_master: {res}")
    return res


def room_start(token: str, room_id: int):
    """live start"""
    with engine.begin() as conn:
        user = get_user_by_token(token)
        "get room master"
        result = conn.execute(
            text(
                """
                SELECT `room_master` FROM `room` WHERE id=:room_id
                """
            ),
            {"room_id": room_id},
        ).one()
        res = result[0]
        print(f"room master is: {res}")
        if res == user.id:
            update_room_status(conn, room_id, WaitRoomStatus.LiveStart)
        conn.commit()


def room_end(token: str, room_id: int, score_judge: list[int], score: int):
    with engine.begin() as conn:
        user = get_user_by_token(token)
        print(f"room end: {user.id}, {room_id}, {score_judge}")
        row = score_judge
        print(f"result perfect: {row[0]}")
        print(f"result great: {row[1]}")
        print(f"result good: {row[2]}")
        print(f"result bad: {row[3]}")
        print(f"result miss: {row[4]}")
        print(f"result user_id: {user.id}")
        print(f"result score: {score}")
        conn.execute(
            text(
                """
                UPDATE `room_member` SET score=:score, perfect=:perfect, great=:great, good=:good, bad=:bad, miss=:miss
                WHERE room_id=:room_id AND user_id=:user_id
                """
            ),
            {"score": score, "perfect": row[0], "great": row[1], "good": row[2], "bad": row[3], "miss": row[4], "room_id": room_id, "user_id": user.id},
        )
        conn.commit()


class ScoreList(BaseModel, strict=True):
    user_id: int
    judge_count_list: list[int]
    score: int


def room_result(token: str, room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT user_id, perfect, great, good, bad, miss, score FROM `room_member` WHERE room_id=:room_id AND score > -1
                """
            ),
            {"room_id": room_id},
        )

        user_result: list[ScoreList] = []

        print(f"result count: {result.rowcount}")
        if result.rowcount != get_room_user_count(conn, room_id):
            print("no match count")
            return user_result
        res = result.fetchall()
        print(f"res: {res}")
        for row in res:
            print(f"result perfect: {row.perfect}")
            print(f"result great: {row.great}")
            print(f"result good: {row.good}")
            print(f"result bad: {row.bad}")
            print(f"result miss: {row.miss}")
            print(f"result user_id: {row.user_id}")
            print(f"result score: {row.score}")
            score_list = [
                row.perfect,
                row.great,
                row.good,
                row.bad,
                row.miss,
            ]
            user_id = row.user_id
            score = row.score

            user_list = (
                ScoreList(
                    user_id=user_id,
                    judge_count_list=score_list,
                    score=score,
                )
            )
            user_result.append(user_list)

        """
        conn.execut(
            text(
                #DELETE FROM `room_member` WHERE room_id=:room_id
            ),
            {"room_id", room_id},
        )
        conn.execute(
            text(
                #DELETE FROM `room` WHERE id=:room_id
            ),
            {"room_id": room_id}
        )
        """
        conn.commit()
        return user_result


def room_leave(token: str, room_id: int):
    with engine.begin() as conn:
        user = get_user_by_token(token)
        "get room master"
        result = conn.execute(
            text(
                """
                SELECT `room_master` FROM `room` WHERE id=:room_id
                """
            ),
            {"room_id": room_id},
        ).one()
        res = result[0]
        ch_host_judge = False
        if res == user.id:
            ch_host_judge = True

        result = conn.execute(
            text(
                """
                SELECT user_id FROM `room_member` WHERE room_id=:room_id AND user_id=:user_id
                """
            ),
            {"room_id": room_id, "user_id": user.id}
        ).one_or_none()
        if result is None:
            print("you already leave")
            return None
        user_id = result[0]

        conn.execute(
            text(
                """
                DELETE FROM `room_member` WHERE room_id=:room_id AND user_id=:user_id
                """
            ),
            {"room_id": room_id, "user_id": user_id},
        )
        down_joined_count(conn, room_id)

        count = get_room_user_count(conn, room_id)
        conn.commit()
        print(f"room leave upto user: {count}")
        if count > 0:
            if ch_host_judge == 1:
                chenge_host_in_room(conn, room_id)
        """
        else:
            conn.execute(
                text(
                    #DELETE FROM `room` WHERE id=:room_id
                ),
                {"room_id": room_id},
            )
        """
        conn.commit()


def chenge_host_in_room(conn, room_id: int):
    print("chenge host in room")
    result = conn.execute(
        text(
            """
            SELECT user_id FROM `room_member` WHERE room_id=:room_id ORDER BY in_order LIMIT 1
            """
        ),
        {"room_id": room_id},
    ).one_or_none()
    if result is None:
        return None
    res = result[0]
    print(f"next host is: {res}")
    conn.execute(
        text(
            """
            UPDATE `room` SET room_master=:room_master WHERE id=:room_id
            """
        ),
        {"room_master": res, "room_id": room_id},
    )
    conn.commit()
    return res
