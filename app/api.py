from enum import Enum

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
async def root():
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest):
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
def user_me(token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=404)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def user_update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()


# Room API


class RoomCreateRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID
    select_difficulty: LiveDifficulty  # 選択難易度


class RoomCreateResponse(BaseModel):
    room_id: int  # 発行されたルームのID（以後の通信はこのiDを添える）


@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    """ルーム作成リクエスト"""
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]  # 入場可能なルーム一覧


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest, token: str = Depends(get_auth_token)):
    """入場可能なルーム一覧を取得"""
    live_id = req.live_id
    room_info_list = model.get_room_info_list(token, live_id)
    return RoomListResponse(room_info_list=room_info_list)


class RoomJoinRequest(BaseModel):
    room_id: int  # 入るルーム
    select_difficulty: LiveDifficulty  # 選択難易度


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult  # ルーム入場結果


@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    """ルーム入場リクエスト"""
    join_room_result = model.join_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=join_room_result)


class RoomWaitRequest(BaseModel):
    room_id: int  # 対象ルーム


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus  # 結果
    room_user_list: list[RoomUser]  # ルームに居るプレイヤー一覧


@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    """４人集まるのを待つ（ポーリング）。APIの結果でゲーム開始がわかる"""
    status, room_user_list = model.get_room_wait_status(token, req.room_id)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class RoomStartRequest(BaseModel):
    room_id: int  # 対象ルーム


@app.post("/room/start", response_model=Empty)
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    """ルームのライブ開始リクエスト。部屋のオーナーが叩く"""
    model.start_room(token, req.room_id)
    return Empty()


class RoomEndtRequest(BaseModel):
    room_id: int  # 対象ルーム
    judge_count_list: list[int]  # 各判定数
    score: int  # スコア


@app.post("/room/end", response_model=Empty)
def room_end(req: RoomEndtRequest, token: str = Depends(get_auth_token)):
    """ルームのライブ終了時リクエスト。ゲームが終わったら各人が叩く。"""
    model.end_room(token, req.room_id, req.judge_count_list, req.score)
    return Empty()


class RoomResultRequest(BaseModel):
    room_id: int  # 対象ルーム


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]  # 自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest, token: str = Depends(get_auth_token)):
    """ルームのライブ終了後。end 叩いたあとにこれをポーリングする。 クライアントはn秒間隔で投げる想定。"""
    result_user_list = model.get_room_result(token, req.room_id)
    return RoomResultResponse(result_user_list=result_user_list)
