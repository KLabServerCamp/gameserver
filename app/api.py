from fastapi import FastAPI
from pydantic import BaseModel, Field

from . import service
from .auth import SafeUser
from . import model

# from typing import List

app = FastAPI(debug=True)


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
    token = service.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


# 認証のサンプルAPI
# ゲームでは使わない
@app.get("/user/me")
def user_me(user: SafeUser) -> SafeUser:
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update")
def update(user: SafeUser, req: UserCreateRequest) -> Empty:
    service.update_user(user.id, req.user_name, req.leader_card_id)
    return Empty()


# Room APIs


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: model.LiveDifficulty


class RoomID(BaseModel):
    room_id: int


# ルームを新規で建てる。
@app.post("/room/create")
def create(user: SafeUser, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    room_id = service.create_room(req.live_id, user.id, req.select_difficulty)
    return RoomID(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[service.RoomInfo]


# 入場可能なルーム一覧を取得
@app.post("/room/list")
def room_list(user:  SafeUser, req: RoomListRequest) -> RoomListResponse:
    print("/room/list", req)
    room_infos = service.get_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_infos)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: model.LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: service.JoinRoomResult


# 上記listのルームに入場。
@app.post("/room/join")
def join(user: SafeUser, req: RoomJoinRequest) -> RoomJoinResponse:
    print("/room/join", req)
    return RoomJoinResponse(
        join_room_result=service.join_room(
            req.room_id, user.id, req.select_difficulty))


class RoomWaitResponse(BaseModel):
    status: model.WaitRoomStatus
    room_user_list: list[service.RoomUser]


# ルーム待機中（ポーリング）。APIの結果でゲーム開始がわかる。 クライアントはn秒間隔で投げる想定。
@app.post("/room/wait")
def wait(user: SafeUser, req: RoomID) -> RoomWaitResponse:
    print("/room/wait", req)
    status, users = service.wait_room(req.room_id, user.id)
    return RoomWaitResponse(status=status, room_user_list=users)


# ルームのライブ開始。部屋のオーナーがたたく。
@app.post("/room/start")
def start(user: SafeUser, req: RoomID) -> Empty:
    print("/room/start", req)
    service.start_room(req.room_id, user.id)
    return Empty()


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


# ルームのライブ終了時リクエスト。ゲーム終わったら各人が叩く。
@app.post("/room/end")
def end(user: SafeUser, req: RoomEndRequest) -> Empty:
    print("/room/end", req)
    service.end_room(req.room_id, user.id, req.score, req.judge_count_list)
    return Empty()


class RoomResultResponse(BaseModel):
    result_user_list: list[service.ResultUser]


# ルームのライブ終了後。end 叩いたあとにこれをポーリングする。 クライアントはn秒間隔で投げる想定。
@app.post("/room/result")
def result(user: SafeUser, req: RoomID) -> RoomResultResponse:
    print("/room/result", req)
    return RoomResultResponse(
        result_user_list=service.result_room(req.room_id))


# ルーム退出リクエスト。オーナーも /room/join で参加した参加者も実行できる。
@app.post("/room/leave")
def leave(user: SafeUser, req: RoomID) -> Empty:
    print("/room/leave", req)
    service.leave_room(req.room_id, user.id)
    return Empty()
