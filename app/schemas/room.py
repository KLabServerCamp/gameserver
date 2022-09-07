from enum import IntEnum

from pydantic import BaseModel, Field

from ..schemas import user as user_schemas


class JoinRoomResult(IntEnum):
    """ルームに参加した結果"""

    OK = 1
    """入場OK"""
    ROOM_FULL = 2
    """満員"""
    DISBANDED = 3
    """解散済み"""
    OTHER_ERROR = 4
    """その他エラー"""


class WaitRoomStatus(IntEnum):
    """ルーム待機中の状態"""

    WAITING = 1
    """ホストがライブ開始ボタン押すのを待っている"""
    LIVE_START = 2
    """ライブ画面遷移OK"""
    DISSOLUTION = 3
    """解散された"""


class RoomInfo(BaseModel):
    """ルーム情報"""

    room_id: int = Field(description="部屋識別子")
    live_id: int = Field(description="プレイ対象の楽曲識別子")
    joined_user_count: int = Field(description="部屋に入っている人数")
    max_user_count: int = Field(description="部屋の最大人数")

    class Config:
        orm_mode = True


class RoomCreateRequest(BaseModel):
    """Room作成時のリクエスト"""

    live_id: int = Field(description="ルームで遊ぶ楽曲のID")
    select_difficulty: user_schemas.LiveDifficulty = Field(description="選択難易度")


class RoomCreateResponse(BaseModel):
    """Room作成時のレスポンス"""

    room_id: int = Field(description="発行されたルームのID（以後の通信はこのiDを添える）")


class RoomListRequest(BaseModel):
    """Room一覧取得時のリクエスト"""

    live_id: int = Field(description="ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）")


class RoomListResponse(BaseModel):
    """Room一覧取得時のレスポンス"""

    room_info_list: list[RoomInfo] = Field(description="ルーム一覧")


class RoomJoinRequest(BaseModel):
    """Room参加時のリクエスト"""

    room_id: int = Field(description="入るルーム")
    select_difficulty: user_schemas.LiveDifficulty = Field(description="選択難易度")


class RoomJoinResponse(BaseModel):
    """Room参加時のレスポンス"""

    join_room_result: JoinRoomResult = Field(description="ルーム入場結果")


class RoomWaitRequest(BaseModel):
    """ルーム待機時のリクエスト"""

    room_id: int = Field(description="対象ルーム")


class RoomWaitResponse(BaseModel):
    """ルーム待機時のレスポンス"""

    status: WaitRoomStatus = Field(description="参加しているルームの状態")
    room_user_list: list[user_schemas.RoomUser] = Field(description="ルームにいるプレイヤー一覧")


class RoomStartRequest(BaseModel):
    """ルーム開始時のリクエスト"""

    room_id: int = Field(description="対象ルーム")


class RoomEndRequest(BaseModel):
    """ルームのライブ終了時リクエスト"""

    room_id: int = Field(description="対象ルーム")
    judge_count_list: list[int] = Field(description="各判定数")
    score: int = Field(description="スコア")


class RoomResultRequest(BaseModel):
    """ルームの結果取得時のリクエスト

    /room/end 叩いたあとにこれをポーリングする。 クライアントはn秒間隔で投げる想定。
    """

    room_id: int = Field(description="対象ルーム")


class RoomResultResponse(BaseModel):
    """ルームの結果取得時のレスポンス"""

    result_user_list: list[user_schemas.ResultUser] = Field(
        description="自身を含む各ユーザーの結果※全員揃っていない待機中は[]が返却される想定"
    )


class RoomLeaveRequest(BaseModel):
    """ルームの退出時のリクエスト"""

    room_id: int = Field(description="対象ルーム")
