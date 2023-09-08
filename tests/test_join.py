from fastapi.testclient import TestClient

from app import schemas
from app.api import app

client = TestClient(app)
user_tokens = []


def _create_users():
    for i in range(10):
        response = client.post(
            "/user/create",
            json={"user_name": f"room_user_{i}", "leader_card_id": 1000},
        )
        user_tokens.append(response.json()["user_token"])


_create_users()


def _auth_header(i=0):
    token = user_tokens[i]
    return {"Authorization": f"bearer {token}"}


def test_join():
    # user 0 が create する
    response = client.post(
        "/room/create",
        headers=_auth_header(0),
        json={"live_id": 1001, "select_difficulty": 1},
    )
    assert response.status_code == 200

    room_id = response.json()["room_id"]
    print(f"room/create {room_id=}")

    response = client.post("/room/list", json={"live_id": 1001})
    assert response.status_code == 200
    print("room/list response:", response.json())

    # 2 人入れる
    for i in range(1, 3):
        response = client.post(
            "/room/join",
            headers=_auth_header(i),
            json={"room_id": room_id, "select_difficulty": 2},
        )
        assert response.json()["join_room_result"] == schemas.JoinRoomResult.Ok
        print("room/join", i, response.json())

    # 既に入っているはずの user を再度 join
    for i in range(3):
        response = client.post(
            "/room/join",
            headers=_auth_header(i),
            json={"room_id": room_id, "select_difficulty": 2},
        )
        # OtherError を返すはず
        assert response.json()["join_room_result"] == schemas.JoinRoomResult.OtherError
        print("room/join", i, response.json())

    # 4 人目を入れる
    response = client.post(
        "/room/join",
        headers=_auth_header(3),
        json={"room_id": room_id, "select_difficulty": 2},
    )
    assert response.json()["join_room_result"] == schemas.JoinRoomResult.Ok
    print("room/join", 3, response.json())

    # 5 人目を入れる
    response = client.post(
        "/room/join",
        headers=_auth_header(4),
        json={"room_id": room_id, "select_difficulty": 2},
    )
    assert response.json()["join_room_result"] == schemas.JoinRoomResult.RoomFull
    print("room/join full", response.json())

    # 既に RoomFull のときに、既に join 済みの user を join しようとしても RoomFull が返ってくる
    # （ RoomFull の判定を先に行っているので）
    response = client.post(
        "/room/join",
        headers=_auth_header(1),
        json={"room_id": room_id, "select_difficulty": 2},
    )
    assert response.json()["join_room_result"] == schemas.JoinRoomResult.RoomFull
    print("room/join full", response.json())

    # live 開始
    response = client.post(
        "/room/start", headers=_auth_header(0), json={"room_id": room_id}
    )
    assert response.status_code == 200
    print("room/wait response:", response.json())

    # live が始まっている部屋に 6 人目を join
    response = client.post(
        "/room/join",
        headers=_auth_header(5),
        json={"room_id": room_id, "select_difficulty": 1},
    )
    # room.status=1 以外は Disbanded
    assert response.json()["join_room_result"] == schemas.JoinRoomResult.Disbanded
    print("room/join full", response.json())

    # 全員のスコアを入れる
    for i in range(4):
        response = client.post(
            "/room/end",
            headers=_auth_header(i),
            json={
                "room_id": room_id,
                "score": i,
                "judge_count_list": [i, i, i, i, i],
            },
        )
        assert response.status_code == 200
        print("room/end response:", response.json())

    response = client.post(
        "/room/result",
        json={"room_id": room_id},
    )
    assert response.status_code == 200
    print("room/end response:", response.json())

    # live が終了した部屋に 7 人目を join
    response = client.post(
        "/room/join",
        headers=_auth_header(6),
        json={"room_id": room_id, "select_difficulty": 1},
    )
    assert response.json()["join_room_result"] == schemas.JoinRoomResult.Disbanded
    print("room/join full", response.json())
