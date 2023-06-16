import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
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


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(req, exc):
    print("Request validation error")
    print(f"{req.url=}\n{exc.body=}\n{exc=!s}")
    return await fastapi.exception_handlers.request_validation_exception_handler(
        req, exc
    )


# Sample API
@app.get("/")
async def root() -> dict:
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str = Field(title="ユーザー名")
    leader_card_id: int = Field(title="リーダーカードのID")


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create")
def user_create(req: UserCreateRequest) -> UserCreateResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


# 認証のサンプルAPI
# ゲームでは使わない
@app.get("/user/me")
def user_me(token: UserToken) -> SafeUser:
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


class ListRoomRequest(BaseModel):
    live_id: int


class JoinRoomRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_users: list[RoomUser]


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


@app.post("/room/list")
def list_room(req: ListRoomRequest) -> list[RoomInfo]:
    """ルーム一覧取得リクエスト"""
    rooms = model.room_search(req.live_id)
    return rooms


@app.post("/room/join")
def join_room(req: JoinRoomRequest, token: UserToken) -> JoinRoomResult:
    """ルーム入室リクエスト"""
    print("/room/join", req)
    join_room_result = model.join_room(token, req.room_id, req.select_difficulty)
    return join_room_result


@app.post("/room/wait")
def wait_room(req: RoomID, token: UserToken) -> RoomWaitResponse:
    """ルーム待機中(n秒ごとにポーリング)"""
    print("/room/wait", req)
    status, room_user_list = model.room_wait_status(token, req.room_id)
    return RoomWaitResponse(status=status, room_users=room_user_list)


@app.post("/room/start")
def start_room(req: RoomID, token: UserToken) -> Empty:
    """ライブ開始リクエスト"""
    print("/room/start", req)
    model.room_start(token, req.room_id)
    return Empty()


@app.post("/room/end")
def end_room(req: RoomEndRequest, token: UserToken) -> Empty:
    """ライブ終了リクエスト"""
    print("/room/end", req)
    model.room_end(token, req.room_id, req.judge_count_list, req.score)
    return Empty()


@app.post("/room/result")
def result_room(req: RoomID, token: UserToken) -> list[ResultUser]:
    """リザルト表示リクエスト(n秒ごとにポーリング)"""
    print("/room/result", req)
    result = model.room_result(token, req.room_id)
    return result
