from enum import IntEnum

from pydantic import BaseModel, Field


class LiveDifficulty(IntEnum):
    """プレイする楽曲の難易度"""

    NORMAL = 1
    """ノーマル難易度"""
    HARD = 2
    """ハード難易度"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int = Field(description="ユーザー識別子")
    name: str = Field(description="ユーザー名")
    leader_card_id: int = Field(description="設定アバター")

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    """ルームに参加しているユーザー"""

    user_id: int = Field(description="ユーザー識別子")
    name: str = Field(description="ユーザ名")
    leader_card_id: int = Field(description="設定アバター")
    select_difficulty: LiveDifficulty = Field(description="選択難易度")
    is_me: bool = Field(description="リクエストを投げたユーザと同じか")
    is_host: bool = Field(description="部屋を立てた人か")

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    """ユーザのスコア情報"""

    user_id: int = Field(description="ユーザー識別子")
    judge_count_list: list[int] = Field(description="各判定数（良い判定から昇順）")
    score: int = Field(description="スコア")

    class Config:
        orm_mode = True


class UserCreateRequest(BaseModel):
    """ユーザー作成時のリクエスト"""

    user_name: str = Field(description="ユーザー名")
    leader_card_id: int = Field(description="設定アバター")


class UserCreateResponse(BaseModel):
    """ユーザー作成時のレスポンス"""

    user_token: str = Field(description="発行されたユーザートークン（以後の通信はこのトークンを添える）")
