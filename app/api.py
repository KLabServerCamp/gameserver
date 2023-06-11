from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from enum import Enum

from . import model
from .auth import UserToken
from .model import LiveDifficulty

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


class LiveDifficult(Enum):
    normal = 1
    hard = 2


class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


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
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


# 入場可能なルーム一覧を取得
# Request --------------
# live_id 	int 	ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）
# Response -------------
# room_info_list 	list[RoomInfo] 	入場可能なルーム一覧
@app.post("/room/list")
def list(token: UserToken, req: RoomListRequest) -> RoomListResponse:
    print("/room/list", req)


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
def join(token: UserToken, req: RoomJoinRequest) -> RoomJoinResponse:
    print("/room/join", req)


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


# ルーム待機中（ポーリング）。APIの結果でゲーム開始がわかる。 クライアントはn秒間隔で投げる想定。
# Request --------------
# room_id 	int 	対象ルーム
# Response -------------
# status 	WaitRoomStatus 	結果
# room_user_list 	list[RoomUser] 	ルームにいるプレイヤー一覧
@app.post("/room/wait")
def wait(token: UserToken, req: RoomID) -> RoomWaitResponse:
    print("/room/wait", req)


# ルームのライブ開始。部屋のオーナーがたたく。
# Request --------------
# room_id 	int 	対象ルーム
@app.post("/room/start")
def start(token: UserToken, req: RoomID) -> Empty:
    print("/room/start", req)


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


# /room/end
# ルームのライブ終了時リクエスト。ゲーム終わったら各人が叩く。
# Request --------------
# room_id 	int 	対象ルーム
# judge_count_list 	list[int] 	各判定数
# score 	int 	スコア
@app.post("/room/end")
def end(token: UserToken, req: RoomEndRequest) -> Empty:
    print("/room/end", req)


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


# /room/result
# ルームのライブ終了後。end 叩いたあとにこれをポーリングする。 クライアントはn秒間隔で投げる想定。
# Request --------------
# room_id 	int 	対象ルーム
# Response -------------
# result_user_list 	list[ResultUser] 	自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定
@app.post("/room/result")
def result(token: UserToken, req: RoomID) -> RoomResultResponse:
    print("/room/result", req)


# /room/leave
# ルーム退出リクエスト。オーナーも /room/join で参加した参加者も実行できる。
# Request --------------
# room_id 	int 	対象ルーム
@app.post("/room/leave")
def leave(toekn: UserToken, req: RoomID) -> Empty:
    print("/room/leave", req)
