from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .. import model
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

router = APIRouter()
bearer = HTTPBearer()


def get_auth_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status_code=401, detail="invalid credential")
    return cred.credentials


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: model.LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_list: list[model.RoomInfo]


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: model.LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: model.JoinRoomResult


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: model.WaitRoomStatus
    room_user_list: list[model.RoomUser]


class Empty(BaseModel):
    pass


@router.post("/room/create", tags=["room"], response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token=Depends(get_auth_token)):
    return RoomCreateResponse(
        room_id=model.create_room(req.live_id, req.select_difficulty, token)
    )


@router.post("/room/list", tags=["room"], response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    return RoomListResponse(room_list=model.get_room_list(req.live_id))


@router.post("/room/join", tags=["room"], response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token=Depends(get_auth_token)):
    return RoomJoinResponse(join_room_result=model.join_room(req.room_id, req.select_difficulty, token))


@router.post("/room/wait", tags=["room"], response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token=Depends(get_auth_token)):
    status, room_user_list = model.get_room_wait(req.room_id, token)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)