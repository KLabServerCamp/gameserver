from pydantic import BaseModel

from .room import (
    JoinRoomResult,
    RoomCreateRequest,
    RoomCreateResponse,
    RoomEndRequest,
    RoomInfo,
    RoomJoinRequest,
    RoomJoinResponse,
    RoomLeaveRequest,
    RoomListRequest,
    RoomListResponse,
    RoomResultRequest,
    RoomResultResponse,
    RoomStartRequest,
    RoomWaitRequest,
    RoomWaitResponse,
    WaitRoomStatus,
)
from .user import (
    LiveDifficulty,
    ResultUser,
    RoomUser,
    SafeUser,
    UserCreateRequest,
    UserCreateResponse,
)


class Empty(BaseModel):
    """空のレスポンス"""

    pass
