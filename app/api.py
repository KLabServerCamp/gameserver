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
    WaitRoomStatus,
)

app = FastAPI()


# リクエストのvalidation errorをprintする
# このエラーが出たら、リクエストのModel定義が間違っている
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


class RoomListRequest(BaseModel):
    live_id: int


class RoomInfoList(BaseModel):
    room_info_list: list[RoomInfo]


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResult(BaseModel):
    join_room_result: JoinRoomResult


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class RoomStartRequest(BaseModel):
    room_id: int


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    # Perfect, Great, Good, Bad, Miss
    score: int


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponce(BaseModel):
    result_user_list: list[ResultUser]


class RoomLeaveRequest(BaseModel):
    room_id: int


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


@app.post("/room/list")
def room_list(req: RoomListRequest) -> RoomInfoList:
    print("/room/create", req)
    room_info_list = model.list_room(req.live_id)
    return RoomInfoList(room_info_list=room_info_list)


@app.post("/room/join")
def room_join(token: UserToken, req: RoomJoinRequest) -> RoomJoinResult:
    print("/room/join", req)
    join_room_result = model.join_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResult(join_room_result=join_room_result)


@app.post("/room/wait")
def wait_room(token: UserToken, req: RoomWaitRequest) -> RoomWaitResponse:
    status, users = model.wait_room(token, req.room_id)
    return RoomWaitResponse(status=status, room_user_list=users)


@app.post("/room/start")
def start_room(token: UserToken, req: RoomStartRequest) -> Empty:
    model.room_start(token, req.room_id)
    return Empty()


@app.post("/room/end")
def end_room(token: UserToken, req: RoomEndRequest) -> Empty:
    model.room_end(token, req.room_id, req.judge_count_list, req.score)
    return Empty()


@app.post("/room/result")
def result_room(req: RoomResultRequest) -> RoomResultResponce:
    result_user_list = model.room_result(req.room_id)
    return RoomResultResponce(result_user_list=result_user_list)


@app.post("/room/leave")
def leave_room(token: UserToken, req: RoomLeaveRequest) -> Empty:
    model.room_leave(token, req.room_id)
    return Empty()
