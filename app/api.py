import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
from .model import (
    LiveDifficulty,
    RoomListRequest,
    RoomListResponse,
    RoomJoinRequest,
    RoomJoinResponse,
    RoomLeaveRequest,
    RoomWaitRequest,
    RoomWaitResponse,
    RoomStartRequest,
    RoomEndRequest,
    RoomResultRequest,
    RoomResultResponse,
)

app = FastAPI()


# リクエストのvalidation errorをprintする
# このエラーが出たら、リクエストのModel定義が間違っている
@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(req, exc):
    print("Request validation error")
    print(f"{req.url=}\n{exc.body=}\n{exc=!s}")
    return await fastapi.exception_handlers. \
        request_validation_exception_handler(
            req, exc
        )


# Sample API
@app.get("/")
async def root() -> dict:
    return {"message": "Hello World"}


# User APIs


# FastAPI 0.100 は model_validate_json() を使わないので、 strict モードにすると
# EnumがValidationエラーになってしまいます。
class UserCreateRequest(BaseModel):
    user_name: str = Field(title="ユーザー名")
    leader_card_id: int = Field(title="リーダーカードのID")


# Responseの方は strict モードを利用できます
class UserCreateResponse(BaseModel, strict=True):
    user_token: str


@app.post("/user/create")
def user_create(req: UserCreateRequest) -> UserCreateResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


# 認証動作確認用のサンプルAPI
# ゲームアプリは使わない
@app.get("/user/me")
def user_me(token: UserToken) -> model.SafeUser:
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # print(f"user_me({token=}, {user=})")
    # 開発中以外は token をログに残してはいけない。
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update")
def update(req: UserCreateRequest, token: UserToken) -> Empty:
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()


# Room APIs


class RoomID(BaseModel):
    room_id: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


@app.post("/room/list")
def room_list(req: RoomListRequest) -> RoomListResponse:
    """ルーム列挙リクエスト"""
    print("/room/list", req)
    res = model.list_room(req)
    return RoomListResponse(room_info_list=res)


@app.post("/room/join")
def room_join(token: UserToken, req: RoomJoinRequest) -> RoomJoinResponse:
    """ルーム入室リクエスト"""
    print("/room/join", req)
    return model.join_room(token, req)


@app.post("/room/leave")
def room_leave(token: UserToken, req: RoomLeaveRequest):
    """ルーム退室リクエスト"""
    print("/room/leave", req)
    model.leave_room(token, req)
    return Empty()


@app.post("/room/wait")
def room_wait(token: UserToken, req: RoomWaitRequest) -> RoomWaitResponse:
    """ルーム待機ポーリング"""
    print("/room/wait", req)
    return model.wait_room(token, req)


@app.post("/room/start")
def room_start(token: UserToken, req: RoomStartRequest):
    """ライブ開始リクエスト"""
    print("/room/start", req)
    model.start_room(token, req)
    return Empty()


@app.post("/room/end")
def room_end(token: UserToken, req: RoomEndRequest):
    """リザルト送信リクエスト"""
    print("/room/end", req)
    model.end_room(token, req)
    return Empty()


@app.post("/room/result")
def room_result(req: RoomResultRequest) -> RoomResultResponse:
    """リザルト受信リクエスト"""
    print("/room/result", req)
    return model.result_room(req)
