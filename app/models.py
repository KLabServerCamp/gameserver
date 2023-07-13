from enum import IntEnum

from pydantic import BaseModel, field_validator, ConfigDict, Field, StrictInt, StrictStr

"""
Enum definitions
"""


class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    """ルーム入場結果"""

    Ok = 1  # 入場OK
    RoomFull = 2  # 満員
    Disbanded = 3  # 解散済み
    OtherError = 4  # その他エラー


class WaitRoomStatus(IntEnum):
    Waiting = 1  # ホストがライブ開始ボタン押すのを待っている
    LiveStart = 2  # ライブ画面遷移OK
    Dissolution = 3  # 解散された


"""
Models for requests / responses
"""


class StrictBase(BaseModel):
    """DBを利用するためのBaseModel"""

    # strictモードを有効にする
    model_config = ConfigDict(strict=True)


class Empty(StrictBase):
    pass


class SafeUser(StrictBase):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


class UserCreateRequest(StrictBase):
    user_name: str = Field(title="ユーザー名")
    leader_card_id: int = Field(title="リーダーカードのID")


class UserCreateResponse(StrictBase):
    user_token: str


class RoomID(StrictBase):
    room_id: int


class CreateRoomRequest(BaseModel):
    live_id: StrictInt
    select_difficulty: LiveDifficulty


class RoomInfo(StrictBase):
    room_id: int  # 部屋識別子
    live_id: int  # プレイ対象の楽曲識別子
    joined_user_count: int  # 部屋に入っている人数
    max_user_count: int  # 部屋の最大人数


class RoomListRequest(StrictBase):
    live_id: int = Field(title="ライブID")


class RoomListResponse(StrictBase):
    room_info_list: list[RoomInfo]


class JoinRoomRequest(StrictBase):
    room_id: int
    select_difficulty: LiveDifficulty

    @field_validator("select_difficulty", mode="before")
    def value_to_enum(cls, v):
        if isinstance(v, int):
            return LiveDifficulty(v)
        return v


class JoinRoomResponse(StrictBase):
    join_room_result: JoinRoomResult


class LeaveRoomRequest(StrictBase):
    room_id: int


class RoomUser(BaseModel):
    user_id: StrictInt  # ユーザー識別子
    name: StrictStr  # ユーザー名
    leader_card_id: StrictInt  # 設定アバター
    select_difficulty: LiveDifficulty  # 選択難易度
    is_me: bool  # リクエスト投げたユーザーと同じか
    is_host: bool  # 部屋を立てた人か


class WaitRoomResponse(BaseModel):
    status: WaitRoomStatus  # 結果
    room_user_list: list[RoomUser]  # ルームにいるプレイヤー一覧


class EndRoomRequest(StrictBase):
    room_id: int
    judge_count_list: list[int]
    score: int
    
    @field_validator('judge_count_list')
    def confirm_judge_count_list_length(cls, v):
        if len(v) != 5:
            raise ValueError('judge_count_list must contain five elements perfect, great, good, bad and miss')
        return v


class ResultUser(StrictBase):
    user_id: int  # ユーザー識別子
    judge_count_list: list[int]  # 各判定数（良い判定から昇順）
    score: int  # 獲得スコア


class ResultRoomResponse(StrictBase):
    result_user_list: list[ResultUser]  # 自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定


"""
Exception definitions
"""


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""

    pass
