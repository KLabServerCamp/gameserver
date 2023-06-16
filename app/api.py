from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
from .model import LiveDifficulty
from .model import JoinRoomResult
from .model import WaitRoomStatus

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


class RoomID(BaseModel):
    room_id: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


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


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    model.join_room(token, room_id, req.select_difficulty)
    return RoomID(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@app.post("/room/list")
def room_list(req: RoomListRequest) -> RoomListResponse:
    print("/room/list", req)
    rows = model.get_room_list(req.live_id)
    room_list = []
    for row in rows:
        room_list.append(
            RoomInfo(
                room_id=row.room_id,
                live_id=row.live_id,
                joined_user_count=model.get_user_count_in_room(row.room_id),
                max_user_count=4,
            )
        )

    return RoomListResponse(room_info_list=room_list)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


@app.post("/room/join")
def join(token: UserToken, req: RoomJoinRequest) -> RoomJoinResponse:
    result = model.join_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResponse(int(result))


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


@app.post("/room/wait")
def wait(token: UserToken, req: RoomWaitRequest) -> RoomWaitResponse:
    user = model.get_user_by_token(token)
    status = model.get_wait_room_status(req.room_id)
    members = model.get_wait_room_member(token, req.room_id)
    room_user_list = []
    for member in members:
        room_user_list.append(
            RoomUser(
                user_id=member.user_id,
                name=member.name,
                leader_card_id=member.leader_card_id,
                select_difficulty=member.select_difficulty,
                is_me=member.user_id == user.id,
                is_host=member.is_host,
            )
        )
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class RoomStartRequest(BaseModel):
    room_id: int


@app.post("/room/start")
def start(token: UserToken, req: RoomStartRequest):
    model.room_start(req.room_id)
    return {"success": True}


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/end")
def end(token: UserToken, req: RoomEndRequest):
    model.room_end(token, req.room_id, req.judge_count_list, req.score)
    return {"success": True}


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/room/result")
def result(token: UserToken, req: RoomResultRequest) -> RoomResultResponse:
    members = model.get_room_result(req.room_id)
    results = [
        ResultUser(
            user_id=member.user_id,
            judge_count_list=[],
            score=0,
        )
        for member in members
    ]

    if all(member.game_ended for member in members):
        results = [
            ResultUser(
                user_id=member.user_id,
                judge_count_list=[
                    member.judge_perfect,
                    member.judge_great,
                    member.judge_good,
                    member.judge_bad,
                    member.judge_miss,
                ],
                score=member.score,
            )
            for member in members
        ]

    return RoomResultResponse(result_user_list=results)
