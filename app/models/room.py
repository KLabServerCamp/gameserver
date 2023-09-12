from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app import schemas
from app.config import TIMEOUT_THRESHOLD_SEC
from app.db import engine
from app.exceptions import InvalidToken, RoomNotFound

from .util import (
    _change_room_owner,
    _delete_room,
    _delete_user_from_room,
    _get_room_from_room_id,
    _get_room_users_from_room_id,
    _get_user_by_token,
    _update_room_status,
)


class Room:
    @staticmethod
    def create_room(token: str, live_id: int, difficulty: schemas.LiveDifficulty):
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

    @staticmethod
    def get_room_list(live_id: int) -> list:
        """
        live_id が一致する room を返す
        live_id が 0 ならば全ての room を返す
        """
        with engine.begin() as conn:
            if live_id == 0:
                res = conn.execute(
                    text(
                        """
                         SELECT `room`.`room_id`, `room`.`live_id`, `member`.`cnt` AS `member_count` FROM `room` INNER JOIN (
                            SELECT `room_id`, COUNT(*) AS `cnt` FROM `room_member` GROUP BY `room_id`
                         ) AS `member` ON `room`.`room_id`=`member`.`room_id`
                         """
                    )
                )
            else:
                res = conn.execute(
                    text(
                        """
                         SELECT `room`.`room_id`, `room`.`live_id`, `member`.`cnt` AS `member_count` FROM `room` INNER JOIN (
                            SELECT `room_id`, COUNT(*) AS `cnt` FROM `room_member` GROUP BY `room_id`
                         ) AS `member` ON `room`.`room_id`=`member`.`room_id` AND `room`.`live_id`=:live_id
                         """
                    ),
                    {"live_id": live_id},
                )
            rooms = []
            for room in res:
                rooms.append(
                    schemas.RoomInfo(
                        room_id=room.room_id,
                        live_id=room.live_id,
                        joined_user_count=room.member_count,
                    )
                )
            return rooms

    @staticmethod
    def join_room(
        token: str, room_id: int, difficulty: schemas.LiveDifficulty
    ) -> schemas.JoinRoomResult:
        with engine.begin() as conn:
            user = _get_user_by_token(conn, token)
            if user is None:
                raise InvalidToken

            # ロックをかける
            room = conn.execute(
                text("SELECT * FROM `room` WHERE `room_id`=:room_id FOR UPDATE"),
                {"room_id": room_id},
            ).one_or_none()
            if room is None:
                raise RoomNotFound

            if room.status != 1:
                return schemas.JoinRoomResult.Disbanded

            cnt = conn.execute(
                text("SELECT COUNT(1) FROM `room_member` WHERE `room_id`=:room_id"),
                {"room_id": room_id},
            ).one_or_none()
            if cnt._mapping["COUNT(1)"] >= room.max_user_count:
                return schemas.JoinRoomResult.RoomFull

            is_alrady_joined = conn.execute(
                text(
                    "SELECT COUNT(1) FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
                ),
                {"room_id": room_id, "user_id": user.id},
            ).one_or_none()
            if is_alrady_joined._mapping["COUNT(1)"]:
                return schemas.JoinRoomResult.OtherError

            # joinする
            conn.execute(
                text(
                    "INSERT INTO `room_member` SET `room_id`=:room_id, `user_id`=:user_id, `difficulty`=:difficulty"
                ),
                {"room_id": room_id, "user_id": user.id, "difficulty": int(difficulty)},
            )
            return schemas.JoinRoomResult.Ok

    @staticmethod
    def wait_room(token: str, room_id: int):
        # room_id から参加者を特定
        # それぞれの参加者について情報を取得し、 RoomUser のインスタンスを作る
        with engine.begin() as conn:
            req_user = _get_user_by_token(conn, token)
            if req_user is None:
                raise InvalidToken
            room_user_list: list[schemas.RoomUser] = []
            res = conn.execute(
                text(
                    "SELECT `room_id`, `user_id`, `difficulty` FROM `room_member` WHERE `room_id`=:room_id"
                ),
                {"room_id": room_id},
            )

            room = _get_room_from_room_id(conn, room_id)
            if room is None:
                raise RoomNotFound

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
                    schemas.RoomUser(
                        user_id=user.id,
                        name=user.name,
                        leader_card_id=user.leader_card_id,
                        select_difficulty=schemas.LiveDifficulty(
                            user_in_room.difficulty
                        ),
                        is_me=(user.id == req_user.id),
                        is_host=(user.id == room.owner_id),
                    )
                )
            return room.status, room_user_list

    @staticmethod
    def start_room(token: str, room_id: int):
        with engine.begin() as conn:
            user = _get_user_by_token(conn, token)
            if user is None:
                raise InvalidToken
            room = _get_room_from_room_id(conn, room_id)
            if room is None:
                raise RoomNotFound
            if user.id != room.owner_id:
                raise Exception
            _update_room_status(conn, room_id, schemas.WaitRoomStatus.LiveStart)

    @staticmethod
    def end_room(token: str, room_id: int, score: int, judge_count_list: list[int]):
        # room_member_result テーブルに全部突っ込む
        if len(judge_count_list) != 5:
            raise Exception
        # TODO: どうにかする
        user_judge = schemas.LiveJudge(
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
                raise RoomNotFound
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

    @staticmethod
    def room_result(room_id: int):
        # TODO: タイムアウト処理
        with engine.begin() as conn:
            scores = conn.execute(
                text(
                    "SELECT * FROM `room_member_result` WHERE `room_id`=:room_id ORDER BY `updated_at` DESC"
                ),
                {"room_id": room_id},
            ).all()

            # 最終更新から TIMEOUT_THRESHOLD_SEC 秒以上経過していたらリザルトを表示する

            # JST として解釈（無理矢理過ぎる……）
            least_updated_at: datetime = scores[0].updated_at.astimezone(
                ZoneInfo("Asia/Tokyo")
            ) - timedelta(hours=9)
            now = datetime.now(ZoneInfo("Asia/Tokyo"))
            diff_time: timedelta = now - least_updated_at
            if diff_time.seconds < TIMEOUT_THRESHOLD_SEC:
                return []

            user_results = []
            for result in scores:
                user_results.append(
                    schemas.ResultUser(
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
            _update_room_status(conn, room_id, schemas.WaitRoomStatus.Dissolution)
            return user_results

    @staticmethod
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
                raise RoomNotFound

            users_in_room = _get_room_users_from_room_id(conn, room_id)

            # オーナーが抜ける場合、 room.owner_id を変更
            if user.id == room.owner_id:
                _change_room_owner(conn, room_id, user, users_in_room)

            _delete_user_from_room(conn, room_id, user.id)

            # 元から 1 人以下だった場合
            if len(users_in_room) <= 1:
                _delete_room(conn, room_id)
