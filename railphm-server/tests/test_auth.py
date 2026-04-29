def get_valid_captcha(client):
    response = client.get('/api/v1/auth/captcha')
    body = response.get_json()
    data = body["data"]

    assert response.status_code == 200
    assert body["code"] == 200
    assert data["captcha_id"]
    assert data["captcha_image"].startswith("data:image/png;base64,")
    assert data["captcha_code"]

    return data


def test_get_captcha_success(client):
    data = get_valid_captcha(client)

    assert len(data["captcha_code"]) == 4


def test_login_admin_success(client):
    captcha = get_valid_captcha(client)
    response = client.post('/api/v1/auth/login', json={
        "username": "admin",
        "password": "123456",
        "captcha_id": captcha["captcha_id"],
        "captcha_code": captcha["captcha_code"]
    })
    body = response.get_json()
    data = body["data"]

    assert response.status_code == 200
    assert body["code"] == 200
    assert data["token"] == "mock-token-admin"
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "ADMIN"
    assert "password" not in data["user"]

def test_login_ops_success(client):
    captcha = get_valid_captcha(client)
    response = client.post('/api/v1/auth/login', json={
        "username": "ops",
        "password": "123456",
        "captcha_id": captcha["captcha_id"],
        "captcha_code": captcha["captcha_code"]
    })
    body = response.get_json()
    data = body["data"]

    assert response.status_code == 200
    assert data["token"] == "mock-token-ops"
    assert data["user"]["username"] == "ops"
    assert data["user"]["role"] == "OPS"
    assert data["user"]["display_name"] == "运维用户"

def test_login_wrong_password(client):
    captcha = get_valid_captcha(client)
    response = client.post('/api/v1/auth/login', json={
        "username": "admin",
        "password": "wrong",
        "captcha_id": captcha["captcha_id"],
        "captcha_code": captcha["captcha_code"]
    })
    body = response.get_json()

    assert response.status_code == 401
    assert body["code"] == 401
    assert "用户名或密码错误" in body["message"]

def test_login_missing_username(client):
    response = client.post('/api/v1/auth/login', json={
        "password": "123456"
    })
    body = response.get_json()

    assert response.status_code == 400
    assert body["code"] == 400
    assert "username" in body["message"] or "用户名" in body["message"]

def test_login_missing_password(client):
    response = client.post('/api/v1/auth/login', json={
        "username": "admin"
    })
    body = response.get_json()

    assert response.status_code == 400
    assert body["code"] == 400
    assert "password" in body["message"] or "密码" in body["message"]


def test_login_missing_captcha_id(client):
    response = client.post('/api/v1/auth/login', json={
        "username": "admin",
        "password": "123456",
        "captcha_code": "ABCD"
    })
    body = response.get_json()

    assert response.status_code == 400
    assert body["code"] == 400
    assert "captcha_id" in body["message"] or "验证码" in body["message"]


def test_login_missing_captcha_code(client):
    response = client.post('/api/v1/auth/login', json={
        "username": "admin",
        "password": "123456",
        "captcha_id": "captcha-id"
    })
    body = response.get_json()

    assert response.status_code == 400
    assert body["code"] == 400
    assert "captcha_code" in body["message"] or "验证码" in body["message"]


def test_login_wrong_captcha_code(client):
    captcha = get_valid_captcha(client)
    response = client.post('/api/v1/auth/login', json={
        "username": "admin",
        "password": "123456",
        "captcha_id": captcha["captcha_id"],
        "captcha_code": "WRNG"
    })
    body = response.get_json()

    assert response.status_code == 400
    assert body["code"] == 400
    assert "验证码" in body["message"]


def test_login_captcha_cannot_be_reused(client):
    captcha = get_valid_captcha(client)
    payload = {
        "username": "admin",
        "password": "123456",
        "captcha_id": captcha["captcha_id"],
        "captcha_code": captcha["captcha_code"]
    }

    first_response = client.post('/api/v1/auth/login', json=payload)
    second_response = client.post('/api/v1/auth/login', json=payload)
    second_body = second_response.get_json()

    assert first_response.status_code == 200
    assert second_response.status_code == 400
    assert "失效" in second_body["message"] or "验证码" in second_body["message"]


def test_login_wrong_password_with_valid_captcha(client):
    captcha = get_valid_captcha(client)
    response = client.post('/api/v1/auth/login', json={
        "username": "admin",
        "password": "bad-password",
        "captcha_id": captcha["captcha_id"],
        "captcha_code": captcha["captcha_code"]
    })
    body = response.get_json()

    assert response.status_code == 401
    assert body["code"] == 401
    assert "用户名或密码错误" in body["message"]


def test_login_invalid_captcha_id(client):
    response = client.post('/api/v1/auth/login', json={
        "username": "admin",
        "password": "123456",
        "captcha_id": "not-exists",
        "captcha_code": "ABCD"
    })
    body = response.get_json()

    assert response.status_code == 400
    assert body["code"] == 400
    assert "验证码" in body["message"]


def test_me_admin_success(client):
    response = client.get(
        '/api/v1/auth/me',
        headers={"Authorization": "Bearer mock-token-admin"}
    )
    body = response.get_json()
    data = body["data"]

    assert response.status_code == 200
    assert data["username"] == "admin"
    assert data["role"] == "ADMIN"
    assert "password" not in data

def test_me_ops_success(client):
    response = client.get(
        '/api/v1/auth/me',
        headers={"Authorization": "Bearer mock-token-ops"}
    )
    body = response.get_json()
    data = body["data"]

    assert response.status_code == 200
    assert data["username"] == "ops"
    assert data["role"] == "OPS"

def test_me_missing_token(client):
    response = client.get('/api/v1/auth/me')
    body = response.get_json()

    assert response.status_code == 401
    assert body["code"] == 401
    assert "未登录" in body["message"] or "无效" in body["message"]

def test_me_invalid_token(client):
    response = client.get(
        '/api/v1/auth/me',
        headers={"Authorization": "Bearer invalid-token"}
    )
    body = response.get_json()

    assert response.status_code == 401
    assert body["code"] == 401
    assert "未登录" in body["message"] or "无效" in body["message"]

def test_me_invalid_authorization_format(client):
    response = client.get(
        '/api/v1/auth/me',
        headers={"Authorization": "mock-token-admin"}
    )
    body = response.get_json()

    assert response.status_code == 401
    assert body["code"] == 401

def test_logout_success(client):
    response = client.post('/api/v1/auth/logout')
    body = response.get_json()

    assert response.status_code == 200
    assert body["code"] == 200
    assert body["data"]["logged_out"] is True
