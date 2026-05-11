import pytest

from app.core.errors import BusinessException
from app.service.alert_service import AlertService


@pytest.mark.parametrize(
    "risk_score, expected_generated, expected_level, expected_status",
    [
        (0.10, False, "none", "none"),
        (0.25, False, "none", "none"),
        (0.26, True, "low", "unhandled"),
        (0.44, True, "low", "unhandled"),
        (0.45, True, "medium", "unhandled"),
        (0.64, True, "medium", "unhandled"),
        (0.65, True, "high", "unhandled"),
        (1.0, True, "high", "unhandled"),
        (0.0, False, "none", "none"),
        (-0.2, False, "none", "none"),
        (1.2, True, "high", "unhandled"),
    ],
)
def test_alert_service_evaluate_levels(
    risk_score,
    expected_generated,
    expected_level,
    expected_status,
):
    result = AlertService().evaluate(risk_score)

    assert result["alert_generated"] is expected_generated
    assert result["alert_level"] == expected_level
    assert result["alert_status"] == expected_status


def test_alert_service_none_alert_message():
    result = AlertService().evaluate(0.10)

    assert result["alert_status_text"] == "无"
    assert result["alert_message"] == "当前设备状态正常，暂未生成告警"
    assert result["alert_advice"] == "保持常规监测"


def test_alert_service_low_alert_message():
    result = AlertService().evaluate(0.26)

    assert result["alert_status_text"] == "未处理"
    assert result["alert_message"] == "设备风险开始升高，建议关注"
    assert result["alert_advice"] == "建议持续观察设备风险变化趋势"


def test_alert_service_medium_alert_message():
    result = AlertService().evaluate(0.45)

    assert result["alert_message"] == "设备存在异常风险，建议检查"
    assert result["alert_advice"] == "建议结合历史数据和运行状态进行排查"


def test_alert_service_high_alert_message():
    result = AlertService().evaluate(0.65)

    assert result["alert_message"] == "设备处于高风险状态，请及时处理"
    assert result["alert_advice"] == "建议及时安排检修或重点复核"


@pytest.mark.parametrize("risk_score", [None, "abc"])
def test_alert_service_invalid_risk_score(risk_score):
    with pytest.raises(BusinessException):
        AlertService().evaluate(risk_score)
