CREATE DATABASE IF NOT EXISTS railphm
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE railphm;

DROP TABLE IF EXISTS phm_alert_record;

CREATE TABLE phm_alert_record (
    alert_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '告警ID',

    risk_result_id BIGINT DEFAULT NULL COMMENT '关联风险预测结果ID',
    device_id BIGINT DEFAULT NULL COMMENT '设备主键ID',
    device_code VARCHAR(64) NOT NULL COMMENT '系统设备编号',

    alert_level VARCHAR(32) NOT NULL COMMENT '告警等级：low、medium、high',
    alert_status VARCHAR(32) NOT NULL DEFAULT 'unhandled' COMMENT '告警状态：unhandled、processing、resolved',
    alert_status_text VARCHAR(32) DEFAULT '未处理' COMMENT '告警状态文本',
    alert_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '告警产生时间',

    alert_message VARCHAR(512) NOT NULL COMMENT '告警消息',
    alert_advice VARCHAR(512) DEFAULT NULL COMMENT '处理建议',

    risk_score DOUBLE DEFAULT NULL COMMENT '触发告警时的风险分数',
    health_score DOUBLE DEFAULT NULL COMMENT '触发告警时的健康度分数',
    health_level VARCHAR(32) DEFAULT NULL COMMENT '触发告警时的健康等级',
    health_status VARCHAR(32) DEFAULT NULL COMMENT '触发告警时的健康状态',

    target_label_value VARCHAR(128) DEFAULT NULL COMMENT '目标标签值或告警部位',
    target_time DATETIME DEFAULT NULL COMMENT '原始样本目标时间',

    handler_id BIGINT DEFAULT NULL COMMENT '处理人ID',
    handle_time DATETIME DEFAULT NULL COMMENT '处理时间',
    handle_desc VARCHAR(512) DEFAULT NULL COMMENT '处理说明',

    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_alert_device_time (device_code, alert_time),
    INDEX idx_alert_status (alert_status),
    INDEX idx_alert_level (alert_level),
    INDEX idx_risk_result_id (risk_result_id),
    INDEX idx_alert_time (alert_time),
    INDEX idx_device_id (device_id),

    CONSTRAINT fk_alert_device
        FOREIGN KEY (device_id) REFERENCES phm_device(device_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT fk_alert_risk_result
        FOREIGN KEY (risk_result_id) REFERENCES phm_risk_result(risk_result_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备告警记录表';