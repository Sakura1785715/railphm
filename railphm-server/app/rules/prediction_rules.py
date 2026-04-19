def clamp_risk_score(risk_score: float) -> float:
    """
    将风险分数限制在 [0, 1] 区间内。
    当前阶段 risk_score 由 AI mock 服务提供，但业务解释规则稳定落在 server 侧。
    """
    normalized_risk_score = float(risk_score)
    return max(0.0, min(1.0, normalized_risk_score))


def calculate_health_score(risk_score: float) -> float:
    """
    健康度计算规则：
    health_score = 100 - risk_score * 100

    先对 risk_score 做 clamp，再保留 1 位小数。
    """
    clamped_risk_score = clamp_risk_score(risk_score)
    return round(100 - clamped_risk_score * 100, 1)


def map_alert_level(health_score: float) -> str:
    """
    告警级别固定映射规则：
    0 <= health_score <= 30   -> HIGH
    30 < health_score <= 70   -> MEDIUM
    70 < health_score <= 100  -> LOW
    """
    normalized_health_score = max(0.0, min(100.0, float(health_score)))

    if 0.0 <= normalized_health_score <= 30.0:
        return "HIGH"
    if 30.0 < normalized_health_score <= 70.0:
        return "MEDIUM"
    return "LOW"
