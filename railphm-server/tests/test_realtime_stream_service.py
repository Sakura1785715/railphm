import pytest

from app.core.errors import BusinessException
from app.service.realtime_stream_service import RealtimeStreamService


def build_prediction_result(sample_index=0, risk_score=0.41):
    return {
        "device_id": "ATP001",
        "sample_index": sample_index,
        "risk_raw": risk_score,
        "risk_score": risk_score,
        "risk_std": 0.03,
        "threshold": 0.26,
        "predicted_label": int(risk_score >= 0.26),
        "model_version": "test-model",
        "window_start_time": "2026-05-01 09:59:30",
        "window_end_time": "2026-05-01 10:00:00",
        "data_source": "model_runtime",
        "uncertainty_method": "mc_dropout",
        "health_score": 59.0,
        "health_level": "attention",
        "health_status": "关注",
        "health_description": "设备风险开始升高，建议持续关注",
        "alert_generated": True,
        "alert_level": "low",
        "alert_status": "unhandled",
        "alert_status_text": "未处理",
        "alert_message": "设备风险开始升高，建议关注",
        "alert_advice": "建议持续观察设备风险变化趋势",
    }


class FakePredictionService:
    calls = []
    should_fail = False

    @staticmethod
    def infer_prediction(request_data):
        FakePredictionService.calls.append(request_data)
        if FakePredictionService.should_fail:
            raise BusinessException(code=502, message="AI 推理服务不可用", status_code=502)
        return build_prediction_result(sample_index=request_data["sample_index"])


@pytest.fixture
def service(app):
    FakePredictionService.calls = []
    FakePredictionService.should_fail = False
    return RealtimeStreamService(prediction_service=FakePredictionService)


def test_start_with_defaults(service):
    data = service.start({})

    assert data["running"] is True
    assert data["stream_id"] == "default"
    assert data["device_id"] == "ATP001"
    assert data["current_sample_index"] == 0


def test_start_with_custom_config(service):
    data = service.start({
        "device_id": "ATP002",
        "start_sample_index": 100,
        "end_sample_index": 105,
        "step": 1,
        "window_minutes": 30,
        "mc_samples": 20,
        "auto_wrap": False,
    })

    assert data["running"] is True
    assert data["device_id"] == "ATP002"
    assert data["start_sample_index"] == 100
    assert data["current_sample_index"] == 100
    assert data["end_sample_index"] == 105


def test_stop(service):
    service.start({})

    data = service.stop()

    assert data["running"] is False


def test_reset_without_sample_index(service):
    service.start({"start_sample_index": 10})
    service.next()

    data = service.reset({})

    assert data["running"] is False
    assert data["current_sample_index"] == 10


def test_reset_with_sample_index(service):
    service.start({"start_sample_index": 10})

    data = service.reset({"sample_index": 22})

    assert data["running"] is False
    assert data["current_sample_index"] == 22


def test_next_success_increments_sample_index(service):
    service.start({"start_sample_index": 5, "step": 2})

    data = service.next()

    assert data["sample_index"] == 5
    assert data["next_sample_index"] == 7
    assert data["risk_score"] == 0.41
    assert data["health_score"] == 59.0
    assert data["alert_level"] == "low"
    assert data["stream_state"]["current_sample_index"] == 7
    assert FakePredictionService.calls[0]["sample_index"] == 5
    assert FakePredictionService.calls[0]["ts_end"] == "2026-05-01 10:00:05"


def test_next_when_not_running_raises(service):
    service.start({})
    service.stop()

    with pytest.raises(BusinessException) as exc_info:
        service.next()

    assert "未启动" in exc_info.value.message


def test_next_stops_after_end_without_wrap(service):
    service.start({
        "start_sample_index": 10,
        "end_sample_index": 10,
        "auto_wrap": False,
    })

    data = service.next()

    assert data["sample_index"] == 10
    assert data["stream_state"]["running"] is False
    assert data["stream_state"]["current_sample_index"] == 11


def test_next_wraps_after_end_when_enabled(service):
    service.start({
        "start_sample_index": 10,
        "end_sample_index": 10,
        "auto_wrap": True,
    })

    data = service.next()

    assert data["sample_index"] == 10
    assert data["stream_state"]["running"] is True
    assert data["stream_state"]["current_sample_index"] == 10


def test_prediction_failure_does_not_increment_or_update_last_result(service):
    service.start({"start_sample_index": 3})
    FakePredictionService.should_fail = True

    with pytest.raises(BusinessException):
        service.next()

    state = service.state()
    assert state["current_sample_index"] == 3
    assert state["last_result"] is None


def test_start_rejects_invalid_config(service):
    with pytest.raises(BusinessException):
        service.start({"end_sample_index": 1, "start_sample_index": 2})

    with pytest.raises(BusinessException):
        service.start({"auto_wrap": "false"})
