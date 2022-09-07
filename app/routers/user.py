from fastapi import APIRouter, Depends

from app import schemas

from .. import model
from ..dependencies import get_auth_token
from ..exceptions import InvalidToken

router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@router.post("/create", response_model=schemas.UserCreateResponse)
def user_create(req: schemas.UserCreateRequest) -> schemas.UserCreateResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return schemas.UserCreateResponse(user_token=token)


@router.get("/me", response_model=schemas.SafeUser)
def user_me(token: str = Depends(get_auth_token)) -> schemas.SafeUser:
    user = model.get_user_by_token(token)
    if user is None:
        raise InvalidToken()
    return user


@router.post("/update", response_model=schemas.Empty)
def update(req: schemas.UserCreateRequest, token: str = Depends(get_auth_token)) -> schemas.Empty:
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return schemas.Empty()
