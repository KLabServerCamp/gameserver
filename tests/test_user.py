from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


def test_create_user__成功():
    response = client.post(
        "/user/create", json={"user_name": "test1", "leader_card_id": 1000}
    )
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"user_token"}

    token = response.json()["user_token"]

    response = client.get("/user/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"id", "name", "leader_card_id"}
    assert response_data["name"] == "test1"
    assert response_data["leader_card_id"] == 1000


def test_update_user__成功():
    response = client.post(
        "/user/create", json={"user_name": "test_update", "leader_card_id": 1000}
    )
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"user_token"}

    token = response.json()["user_token"]

    response = client.get("/user/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"id", "name", "leader_card_id"}

    response = client.post(
        "/user/update",
        json={
            "user_name": "test_update2",
            "leader_card_id": response_data["leader_card_id"],
        },
        headers={"Authorization": f"bearer {token}"},
    )
    assert response.status_code == 200

    response = client.get("/user/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"id", "name", "leader_card_id"}
    assert response_data["name"] == "test_update2"
    assert response_data["leader_card_id"] == 1000


def test_update_user__tokenなしエラー():
    response = client.post(
        "/user/create", json={"user_name": "test_update", "leader_card_id": 1000}
    )
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"user_token"}

    token = response.json()["user_token"]

    response = client.get("/user/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"id", "name", "leader_card_id"}

    response_data = response.json()

    response = client.post(
        "/user/update",
        json={
            "user_name": "test_update2",
            "leader_card_id": response_data["leader_card_id"],
        },
    )
    assert response.status_code == 403
