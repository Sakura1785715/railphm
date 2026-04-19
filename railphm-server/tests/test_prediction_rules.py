from app.rules.prediction_rules import (
    calculate_health_score,
    clamp_risk_score,
    map_alert_level,
)


def test_calculate_health_score_high_risk():
    assert calculate_health_score(0.82) == 18.0


def test_calculate_health_score_medium_risk():
    assert calculate_health_score(0.52) == 48.0


def test_calculate_health_score_low_risk():
    assert calculate_health_score(0.21) == 79.0


def test_map_alert_level_high_boundary():
    assert map_alert_level(30) == "HIGH"


def test_map_alert_level_medium_lower_boundary():
    assert map_alert_level(30.1) == "MEDIUM"


def test_map_alert_level_medium_upper_boundary():
    assert map_alert_level(70) == "MEDIUM"


def test_map_alert_level_low_boundary():
    assert map_alert_level(70.1) == "LOW"


def test_clamp_risk_score_below_zero():
    assert clamp_risk_score(-0.5) == 0.0
    assert calculate_health_score(-0.5) == 100.0


def test_clamp_risk_score_above_one():
    assert clamp_risk_score(1.5) == 1.0
    assert calculate_health_score(1.5) == 0.0
