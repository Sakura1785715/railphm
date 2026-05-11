import pytest

from app.core.errors import BusinessException
from app.service.health_service import HealthService


@pytest.mark.parametrize(
    "risk_score, expected_score, expected_level, expected_status",
    [
        (0.10, 90.0, "normal", "正常"),
        (0.26, 74.0, "attention", "关注"),
        (0.44, 56.0, "attention", "关注"),
        (0.45, 55.0, "warning", "预警"),
        (0.64, 36.0, "warning", "预警"),
        (0.65, 35.0, "critical", "严重"),
        (1.0, 0.0, "critical", "严重"),
        (0.0, 100.0, "normal", "正常"),
        (-0.2, 100.0, "normal", "正常"),
        (1.2, 0.0, "critical", "严重"),
    ],
)
def test_health_service_evaluate_levels(
    risk_score,
    expected_score,
    expected_level,
    expected_status,
):
    result = HealthService().evaluate(risk_score)

    assert result["health_score"] == expected_score
    assert result["health_level"] == expected_level
    assert result["health_status"] == expected_status
    assert result["health_description"]


def test_health_service_normal_description():
    result = HealthService().evaluate(0.10)

    assert result["health_description"] == "设备当前风险较低，运行状态正常"


def test_health_service_attention_description():
    result = HealthService().evaluate(0.26)

    assert result["health_description"] == "设备风险开始升高，建议持续关注"


def test_health_service_warning_description():
    result = HealthService().evaluate(0.45)

    assert result["health_description"] == "设备健康状态下降，建议重点检查"


def test_health_service_critical_description():
    result = HealthService().evaluate(0.65)

    assert result["health_description"] == "设备处于高风险状态，建议及时处理"


@pytest.mark.parametrize("risk_score", [None, "abc"])
def test_health_service_invalid_risk_score(risk_score):
    with pytest.raises(BusinessException):
        HealthService().evaluate(risk_score)
