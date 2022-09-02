from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


def test_create_user():
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


def test_user_not_found() -> None:
    response = client.get("/user/me", headers={"Authorization": f"bearer invalid"})
    assert response.status_code == 404

    response = client.get("/user/me")
    assert response.status_code == 403

    response = client.get("/user/me", headers={"Authorization": f"bearer"})
    assert response.status_code == 403

    response = client.get("/user/me", headers={"Authorization": f"bearer {None}"})
    assert response.status_code == 404


def test_user_update() -> None:
    response = client.post(
        "/user/create", json={"user_name": "test1", "leader_card_id": 1000}
    )
    token = response.json()["user_token"]

    new_uname: str = "test2"
    new_leader_id: int = 2000
    response = client.post(
        "/user/update",
        json={"user_name": new_uname, "leader_card_id": new_leader_id},
        headers={"Authorization": f"bearer {token}"},
    )
    assert response.status_code == 200

    response = client.get("/user/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"id", "name", "leader_card_id"}
    assert response_data["name"] == new_uname
    assert response_data["leader_card_id"] == new_leader_id
