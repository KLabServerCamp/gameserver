from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomID,
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


# === User APIs ===============================================================
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
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# === Room API ================================================================
# Creation
class RoomCreateRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID
    select_difficulty: LiveDifficulty  # 選択難易度


@app.post("/room/create", response_model=RoomID)
def create_room(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    user_id = user_me(token)
    room_id = model.create_room(req.live_id, req.select_difficulty, user_id)
    return RoomID(room_id=room_id)


# List
class RoomListRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]  # 入場可能なルーム一覧


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    rooms = model.get_rooms_by_live_id(req.live_id)
    return RoomListResponse(room_info_list=rooms)


# Join
class RoomJoinRequest(BaseModel):
    room_id: int  # 入るルーム
    select_difficulty: LiveDifficulty  # 選択難易度


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult  # ルーム入場結果


@app.post("/room/join", response_model=RoomJoinResponse)
def join_room(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    user_id = user_me(token)
    room_result = model.join_room(req.room_id, req.select_difficulty, user_id)
    return RoomJoinResponse(join_room_result=room_result)


# Wait
class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus  # 結果
    room_user_list: list[RoomUser]  # ルームにいるプレイヤー一覧


@app.post("/room/wait", response_model=RoomWaitResponse)
def wait_room(req: RoomID, token: str = Depends(get_auth_token)):
    user_id = user_me(token)
    status, room_user_list = model.wait_room(req.room_id, user_id)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


# start
@app.post("/room/start", response_model=Empty)
def start_room(req: RoomID):
    return {}


# end
class RoomEndRequest(BaseModel):
    room_id: int  # 対象ルーム
    judge_count_list: list[int]  # 各判定数
    score: int  # スコア


app.post("/room/end", response_model=Empty)


def end_room(req: RoomEndRequest):
    return {}


# result
class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]  # 自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomID):
    pass


# leave
@app.post("/room/leave", response_model=Empty)
def leave_room(req: RoomID):
    return {}
