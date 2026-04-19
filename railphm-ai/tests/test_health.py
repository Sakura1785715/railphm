def test_health_success(client):
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.get_json()
    assert payload["code"] == 200
    assert payload["message"] == "success"
    assert payload["data"]["service"] == "railphm-ai"
    assert payload["data"]["status"] == "running"
    assert payload["data"]["version"] == "0.1.0"
