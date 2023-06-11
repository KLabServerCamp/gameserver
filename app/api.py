from fastapi import FastAPI
from pydantic import BaseModel, Field

from . import model
from .auth import SafeUser
from .model import LiveDifficulty, JoinRoomResult, WaitRoomStatus
from typing import List

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
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


# 認証のサンプルAPI
# ゲームでは使わない
@app.get("/user/me")
def user_me(user: SafeUser) -> model.SafeUser:
    # print(f"user_me({token=}, {user=})")
    # 開発中以外は token をログに残してはいけない。
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update")
def update(user: SafeUser, req: UserCreateRequest) -> Empty:
    """Update user attributes"""
    # print(req)
    model.update_user(user.id, req.user_name, req.leader_card_id)
    return Empty()


# Room APIs


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count:	int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    id: int
    user_id: int
    judge_count_list: list[int]
    score: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomID(BaseModel):
    room_id: int


# ルームを新規で建てる。
@app.post("/room/create")
def create(user: SafeUser, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: List[RoomInfo]


# 入場可能なルーム一覧を取得
# Request --------------
# live_id 	int 	ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）
# Response -------------
# room_info_list 	list[RoomInfo] 	入場可能なルーム一覧
@app.post("/room/list")
def list(user: SafeUser, req: RoomListRequest) -> RoomListResponse:
    print("/room/list", req)
    # rooms = model.get_room_list_by_room_id(token, req.live_id)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


# 上記listのルームに入場。
# Request --------------
# room_id 	int 	入るルーム
# select_difficulty 	LiveDifficulty 	選択難易度
# Response -------------
# join_room_result 	JoinRoomResult 	ルーム入場結果
@app.post("/room/join")
def join(user: SafeUser, req: RoomJoinRequest) -> RoomJoinResponse:
    print("/room/join", req)


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: List[RoomUser]


# ルーム待機中（ポーリング）。APIの結果でゲーム開始がわかる。 クライアントはn秒間隔で投げる想定。
# Request --------------
# room_id 	int 	対象ルーム
# Response -------------
# status 	WaitRoomStatus 	結果
# room_user_list 	list[RoomUser] 	ルームにいるプレイヤー一覧
@app.post("/room/wait")
def wait(user: SafeUser, req: RoomID) -> RoomWaitResponse:
    print("/room/wait", req)


# ルームのライブ開始。部屋のオーナーがたたく。
# Request --------------
# room_id 	int 	対象ルーム
@app.post("/room/start")
def start(user: SafeUser, req: RoomID) -> Empty:
    print("/room/start", req)


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: List[int]
    score: int


# /room/end
# ルームのライブ終了時リクエスト。ゲーム終わったら各人が叩く。
# Request --------------
# room_id 	int 	対象ルーム
# judge_count_list 	list[int] 	各判定数
# score 	int 	スコア
@app.post("/room/end")
def end(user: SafeUser, req: RoomEndRequest) -> Empty:
    print("/room/end", req)


class RoomResultResponse(BaseModel):
    result_user_list: List[ResultUser]


# /room/result
# ルームのライブ終了後。end 叩いたあとにこれをポーリングする。 クライアントはn秒間隔で投げる想定。
# Request --------------
# room_id 	int 	対象ルーム
# Response -------------
# result_user_list 	list[ResultUser] 	自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定
@app.post("/room/result")
def result(user: SafeUser, req: RoomID) -> RoomResultResponse:
    print("/room/result", req)


# /room/leave
# ルーム退出リクエスト。オーナーも /room/join で参加した参加者も実行できる。
# Request --------------
# room_id 	int 	対象ルーム
@app.post("/room/leave")
def leave(user: SafeUser, req: RoomID) -> Empty:
    print("/room/leave", req)
