from app.service.alert_service import AlertService
from app.service.device_service import DeviceService
from app.service.run_record_service import RunRecordService


ADMIN_HEADERS = {
    "Authorization": "Bearer mock-token-admin"
}

OPS_HEADERS = {
    "Authorization": "Bearer mock-token-ops"
}


def test_business_routes_require_login(client):
    for path in ["/api/v1/devices", "/api/v1/dashboard/overview"]:
        response = client.get(path)
        body = response.get_json()

        assert response.status_code == 401
        assert body["code"] == 401


def test_ops_can_access_business_query_routes(client, monkeypatch):
    monkeypatch.setattr(
        DeviceService,
        "get_device_list",
        staticmethod(lambda **kwargs: {"items": [], "total": 0, "page": 1, "size": 10}),
    )
    monkeypatch.setattr(
        AlertService,
        "get_alert_list",
        staticmethod(lambda *args, **kwargs: {"items": [], "total": 0, "page": 1, "size": 10}),
    )
    monkeypatch.setattr(
        RunRecordService,
        "list_records",
        staticmethod(lambda **kwargs: {"items": [], "total": 0, "page": 1, "page_size": 10}),
    )

    for path in ["/api/v1/devices", "/api/v1/alerts", "/api/v1/run-records"]:
        response = client.get(path, headers=OPS_HEADERS)
        body = response.get_json()

        assert response.status_code == 200
        assert body["code"] == 200


def test_ops_cannot_access_admin_maintenance_route(client):
    response = client.post(
        "/api/v1/devices",
        headers=OPS_HEADERS,
        json={
            "car_no": "CR400AF-RBAC-OPS",
            "atp_type": "CTCS-3",
            "attach_bureau": "北京局",
            "device_status": 1,
        },
    )
    body = response.get_json()

    assert response.status_code == 403
    assert body["code"] == 403
    assert "权限不足" in body["message"]


def test_admin_can_access_admin_maintenance_route(client, monkeypatch):
    monkeypatch.setattr(
        DeviceService,
        "create_device",
        staticmethod(
            lambda payload: {
                "device_id": 9001,
                "car_no": payload["car_no"],
                "atp_type": payload["atp_type"],
                "attach_bureau": payload["attach_bureau"],
                "device_status": payload["device_status"],
            }
        ),
    )

    response = client.post(
        "/api/v1/devices",
        headers=ADMIN_HEADERS,
        json={
            "car_no": "CR400AF-RBAC-ADMIN",
            "atp_type": "CTCS-3",
            "attach_bureau": "北京局",
            "device_status": 1,
        },
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["code"] == 200
    assert body["data"]["device_id"] == 9001


def test_ops_and_admin_can_update_alert_status(client, monkeypatch):
    monkeypatch.setattr(
        AlertService,
        "update_alert_status",
        staticmethod(
            lambda alert_id, payload: {
                "alert_id": alert_id,
                "alert_status": payload["alert_status"],
                "handler_id": payload["handler_id"],
            }
        ),
    )

    for headers in [OPS_HEADERS, ADMIN_HEADERS]:
        response = client.patch(
            "/api/v1/alerts/1/status",
            headers=headers,
            json={
                "alert_status": "PROCESSING",
                "handler_id": 1,
                "handle_note": "权限测试",
            },
        )
        body = response.get_json()

        assert response.status_code == 200
        assert body["code"] == 200
        assert body["data"]["alert_status"] == "PROCESSING"


def test_public_routes_do_not_require_token(client):
    health_response = client.get("/api/v1/health")
    captcha_response = client.get("/api/v1/auth/captcha")

    assert health_response.status_code == 200
    assert health_response.get_json()["code"] == 200
    assert captcha_response.status_code == 200
    assert captcha_response.get_json()["code"] == 200
