from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomInfo,
    RoomUser,
    SafeUser,
    WaitRoomStatus,
)

app = FastAPI()


# Sample APIs


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


class RoomCreateRequest(BaseModel):
    """Room作成時のリクエスト

    Attributes
    ----------
    live_id: int
        ルームで遊ぶ楽曲のID
    select_difficulty: LiveDifficulty
        選択難易度
    """

    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    """Room作成時のレスポンス

    Attributes
    ----------
    room_id: int
        発行されたルームのID（以後の通信はこのiDを添える）
    """

    room_id: int


class RoomListRequest(BaseModel):
    """Room一覧取得時のリクエスト

    Attributes
    ----------
    live_id: int
        ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）
    """

    live_id: int


class RoomListResponse(BaseModel):
    """Room一覧取得時のレスポンス

    Attributes
    ----------
    room_info_list: list[RoomInfo]
        ルーム一覧
    """

    room_info_list: list[RoomInfo]


class RoomJoinRequest(BaseModel):
    """Room参加時のリクエスト

    Attributes
    ----------
    room_id: int
        入るルーム
    select_difficulty: LiveDifficulty
        選択難易度
    """

    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    """Room参加時のレスポンス

    Attributes
    ----------
    join_room_result: JoinRoomResult
        ルーム入場結果
    """

    join_room_result: JoinRoomResult


class RoomWaitRequest(BaseModel):
    """ルーム待機時のリクエスト

    Attributes
    ----------
    room_id: int
        対象ルーム
    """

    room_id: int


class RoomWaitResponse(BaseModel):
    """ルーム待機時のレスポンス

    Attributes
    ----------
    status: WaitRoomStatus
        結果
    room_user_list: list[RoomUser]
        ルームにいるプレイヤー一覧
    """

    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class RoomStartRequest(BaseModel):
    """ルーム開始時のリクエスト

    Attributes
    ----------
    room_id: int
        対象ルーム
    """

    room_id: int


class RoomEndRequest(BaseModel):
    """ルームのライブ終了時リクエスト

    ゲーム終わったら各人が叩く。

    Attributes
    ----------
    room_id: int
        対象ルーム
    judge_count_list: list[int]
        各判定数
    score: int
        スコア
    """

    room_id: int
    judge_count_list: list[int]
    score: int


class RoomResultRequest(BaseModel):
    """ルームの結果取得時のリクエスト

    end 叩いたあとにこれをポーリングする。 クライアントはn秒間隔で投げる想定。

    Attributes
    ----------
    room_id: int
        対象ルーム
    """

    room_id: int


class RoomResultResponse(BaseModel):
    """ルームの結果取得時のレスポンス

    Attributes
    ----------
    result_user_list: list[ResultUser]
        自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定
    """

    result_user_list: list[ResultUser]


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest) -> UserCreateResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


bearer = HTTPBearer()


def get_auth_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status_code=401, detail="invalid credential")
    return cred.credentials


@app.get("/user/me", response_model=SafeUser)
def user_me(token: str = Depends(get_auth_token)) -> SafeUser:
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=404)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)) -> dict:
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# Room APIs


@app.post("/room/create", response_model=RoomCreateResponse)
def create_room(
    req: RoomCreateRequest, token: str = Depends(get_auth_token)
) -> RoomCreateResponse:
    """Roomを作成する"""
    room_id = model.create_room(token, req.live_id)
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        model.insert_room_member(room_id, me.id, req.select_difficulty, is_owner=True)
    return RoomCreateResponse(room_id=room_id)


@app.post("/room/list", response_model=RoomListResponse)
def get_room_list(req: RoomListRequest) -> RoomListResponse:
    room_info_list = model.get_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


@app.post("/room/join", response_model=RoomJoinResponse)
def join_room(
    req: RoomJoinRequest, token: str = Depends(get_auth_token)
) -> RoomJoinResponse:
    """Roomに参加する"""
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        join_room_result = model.join_room(req.room_id, me.id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=join_room_result)


@app.post("/room/wait", response_model=RoomWaitResponse)
def wait_room(
    req: RoomWaitRequest, token: str = Depends(get_auth_token)
) -> RoomWaitResponse:
    """Roomの待機状態を取得する"""
    status = model.get_room_status(req.room_id)
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        room_user_list = model.get_room_user_list(req.room_id, me.id)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


@app.post("/room/start", response_model=Empty)
def start_room(req: RoomStartRequest, token: str = Depends(get_auth_token)) -> Empty:
    """Roomをゲーム開始状態にする"""
    # NOTE:
    # オーナーかどうかを確認する必要があるかも
    model.start_room(req.room_id)
    return Empty()


@app.post("/room/end", response_model=Empty)
def end_room(req: RoomEndRequest, token: str = Depends(get_auth_token)) -> Empty:
    """結果をサーバーに送信する"""
    if len(req.judge_count_list) != 5:
        raise Exception("Length of judge_count_list must be 5.")
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        model.store_score(req.room_id, me.id, req.judge_count_list, req.score)
    return Empty()


@app.post("/room/result", response_model=RoomResultResponse)
def get_room_result(req: RoomResultRequest) -> RoomResultResponse:
    """ルームの結果を取得する"""
    result_user_list = model.get_room_result(req.room_id)
    return RoomResultResponse(result_user_list=result_user_list)
