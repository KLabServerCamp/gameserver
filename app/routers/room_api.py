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


@router.post("/room/create", tags=["room"], response_model=RoomCreateResponse)
def room_list(req: RoomCreateRequest, token=Depends(get_auth_token)):
    return model.create_room(req.live_id, req.select_difficulty, token)
