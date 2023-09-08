import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
from .model import JoinRoomResult, LiveDifficulty, RoomInfo, RoomUser, WaitRoomStatus, ResultUser

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
class CreateUserRequest(BaseModel):
    user_name: str = Field(title="ユーザー名")
    leader_card_id: int = Field(title="リーダーカードのID")


# Responseの方は strict モードを利用できます
class CreateUserResponse(BaseModel, strict=True):
    user_token: str


@app.post("/user/create")
def user_create(req: CreateUserRequest) -> CreateUserResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return CreateUserResponse(user_token=token)


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
def update(req: CreateUserRequest, token: UserToken) -> Empty:
    """ユーザー情報の更新"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()


# Room APIs

# /room/create
class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class CreateRoomResponse(BaseModel):
    room_id: int


# /room/list
class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel, strict=True):
    room_info_list: list[RoomInfo]


# /room/join
class JoinRoomRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class JoinRoomResponse(BaseModel, strict=True):
    join_room_result: JoinRoomResult


# /room/wait
class WaitRoomRequest(BaseModel):
    room_id: int


class WaitRoomResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


# /room/start
class StartRoomRequest(BaseModel):
    room_id: int


# /room/end
class EndRoomRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


# /room/result
class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/room/create")
def room_create(token: UserToken, req: CreateRoomRequest) -> CreateRoomResponse:
    """ルーム作成リクエスト"""
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return CreateRoomResponse(room_id=room_id)


@app.post("/room/list")
def room_list(req: RoomListRequest) -> RoomListResponse:
    room_info_list = model.get_room_list(req.live_id)
    if room_info_list is None:
        raise HTTPException(status_code=404)
    return RoomListResponse(room_info_list=room_info_list)


@app.post("/room/join")
def room_join(token: UserToken, req: JoinRoomRequest) -> JoinRoomResponse:
    """ルーム入室リクエスト"""
    join_room_result = model.join_room(token, req.room_id, req.select_difficulty)

    return JoinRoomResponse(join_room_result=join_room_result)


@app.post("/room/wait")
def room_wait(token: UserToken, req: WaitRoomRequest) -> WaitRoomResponse:
    """4人集まるのを待つ（ポーリング）。APIの結果でゲーム開始がわかる"""
    room_status = model.get_room_status(token, req.room_id)
    room_users = model.get_room_users(token, req.room_id)
    if room_status is None or not room_users:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return WaitRoomResponse(status=room_status, room_user_list=room_users)


@app.post("/room/start")
def room_start(token: UserToken, req: StartRoomRequest) -> Empty:
    """ルームのライブ開始。オーナーが叩く"""
    model.start_room(token, req.room_id)
    return Empty()


@app.post("/room/end")
def room_end(token: UserToken, req: EndRoomRequest) -> Empty:
    """ルームのライブ終了時リクエスト。ゲーム終わったら各人が叩く。"""
    model.end_room(token, req.room_id, req.judge_count_list, req.score)
    return Empty()

