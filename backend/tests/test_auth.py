"""Registration, login, and role checks."""


def test_register_and_me(client):
    created = client.post(
        "/api/auth/register",
        json={
            "full_name": "Meera Nair",
            "email": "meera@example.com",
            "password": "Student@12345",
            "department": "AI and Data Science",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["user"]["role"] == "student"
    assert "password" not in body["user"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "meera@example.com"


def test_invalid_login(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Meera Nair",
            "email": "meera@example.com",
            "password": "Student@12345",
        },
    )
    failed = client.post(
        "/api/auth/login",
        json={"email": "meera@example.com", "password": "Wrong@12345"},
    )
    assert failed.status_code == 401


def test_duplicate_email(client):
    payload = {
        "full_name": "Meera Nair",
        "email": "meera@example.com",
        "password": "Student@12345",
    }
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_student_cannot_list_users(client):
    token = client.post(
        "/api/auth/register",
        json={
            "full_name": "Meera Nair",
            "email": "meera@example.com",
            "password": "Student@12345",
        },
    ).json()["access_token"]
    denied = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 403


def test_missing_token(client):
    assert client.get("/api/auth/me").status_code == 401
