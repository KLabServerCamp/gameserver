import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
from .model import LiveDifficulty

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
    room_id: int = Field(title="部屋ID")


class RoomInfo(BaseModel):
    room_id: int = Field(title="部屋ID")
    live_id: int = Field(title="楽曲ID")
    joined_user_count: int = Field(title="参加済み人数")
    max_user_count: int = Field(title="最大人数")


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class ListRoomRequest(BaseModel):
    live_id: int


class JoinRoomRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class WaitRoomRequest(BaseModel):
    room_id: int


class StartRoomRequest(BaseModel):
    room_id: int


class LeaveRoomRequest(BaseModel):
    room_id: int


class EndRoomRequest(BaseModel):
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
def select(token: UserToken, req: ListRoomRequest) -> list:
    print("/room/list", req)
    room_list = model.list_room(token, req.live_id)
    if room_list is None:
        return []
    room_list = list(map(lambda room: RoomInfo(
            room_id=room.room_id,
            live_id=req.live_id,
            joined_user_count=room.joined_user_count,
            max_user_count=room.max_user_count
            ), room_list))
    return room_list


@app.post("/room/join")
def join(token: UserToken, req: JoinRoomRequest) -> int:
    print("/room/join", req)
    return model.join_room(token, req.room_id, req.select_difficulty)


@app.post("/room/wait")
def join(token: UserToken, req: WaitRoomRequest):
    print("/room/wait", req)
    status, members = model.wait_room(token, req.room_id)
    members = list(map(lambda member: RoomUser(
            user_id=member["user_id"],
            name=member["name"],
            leader_card_id=member["leader_card_id"],
            select_difficulty=member["select_difficulty"],
            is_me=member["is_me"],
            is_host=member["is_host"]
            ), members))
    return {
        "status": status,
        "room_user_list": members
    }


@app.post("/room/start")
def start(token: UserToken, req: StartRoomRequest) -> None:
    print("/room/start", req)
    model.start_room(token, req.room_id)
    return None


@app.post("/room/leave")
def leave(token: UserToken, req: LeaveRoomRequest) -> None:
    print("/room/leave", req)
    model.leave_room(token, req.room_id)
    return None

@app.post("/room/end")
def end(token: UserToken, req: EndRoomRequest) -> None:
    print("/room/end", req)
    model.end_room(token, req.room_id, req.judge_count_list, req.score)
    return None