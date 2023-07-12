from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field, StrictInt

"""
Enum definitions
"""


class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


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


"""
Exception definitions
"""


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""

    pass
