"""
認証モジュール

引数に `token: UserToken` を指定することで認証を行い、そのユーザーの
tokenを取得できる。
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

__all__ = ["UserToken", "InvalidToken"]
bearer = HTTPBearer()


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""

    pass


async def get_auth_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid credential")
    return cred.credentials


UserToken = Annotated[str, Depends(get_auth_token)]
