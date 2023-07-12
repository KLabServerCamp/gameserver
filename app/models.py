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


"""
Exception definitions
"""


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""

    pass
