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

    # test for user me
    token = response.json()["user_token"]

    response = client.get("/user/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"id", "name", "leader_card_id"}
    assert response_data["name"] == "test1"
    assert response_data["leader_card_id"] == 1000

    # test for user update
    response = client.post(
        "user/update",
        headers={"Authorization": f"bearer {token}"},
        json={"user_name": "test2", "leader_card_id": 200},
    )
    assert response.status_code == 200
