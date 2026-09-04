import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_send_signup_otp_success(client):
    response = client.post("/api/auth/send-signup-otp", json={"phone": "+84901234567"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "otp" in body or "message" in body


def test_request_reset_otp_success(client):
    response = client.post("/api/auth/request-reset-otp", json={"phone": "+84901234567"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
