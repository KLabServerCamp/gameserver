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

    response = client.get(
        "/user/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"id", "name", "leader_card_id"}
    assert response_data["name"] == "test1"
    assert response_data["leader_card_id"] == 1000


def test_update_user():
    create_response = client.post(
        "/user/create", json={"user_name": "test2", "leader_card_id": 2000}
    )
    assert create_response.status_code == 200

    data = create_response.json()
    assert data.keys() == {"user_token"}

    token = create_response.json()["user_token"]

    update_response = client.post(
        "/user/update",
        headers={"Authorization": f"bearer {token}"},
        json={"user_name": "test2001", "leader_card_id": 2001},
    )
    assert update_response.status_code == 200

    me_response = client.get("/user/me", headers={
        "Authorization": f"bearer {token}"})

    assert me_response.status_code == 200

    data = me_response.json()
    assert data.keys() == {"id", "name", "leader_card_id"}
    assert data["name"] == "test2001"
    assert data["leader_card_id"] == 2001
