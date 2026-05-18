CREATE DATABASE IF NOT EXISTS railphm
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE railphm;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS phm_alert_record;
DROP TABLE IF EXISTS phm_risk_result;
DROP TABLE IF EXISTS phm_device;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE phm_device (
    device_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '设备ID',
    device_code VARCHAR(64) NOT NULL COMMENT '系统设备编号',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称',
    device_type VARCHAR(64) NOT NULL DEFAULT 'ATP' COMMENT '设备类型',
    device_status TINYINT NOT NULL DEFAULT 1 COMMENT '设备状态：1正常，2关注，3预警，4告警',
    atp_type VARCHAR(64) DEFAULT NULL COMMENT 'ATP类型',
    car_no VARCHAR(64) DEFAULT NULL COMMENT '车号',
    train_no VARCHAR(64) DEFAULT NULL COMMENT '车次',
    attach_bureau VARCHAR(64) DEFAULT NULL COMMENT '配属铁路局',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE INDEX idx_device_code (device_code),
    INDEX idx_device_status (device_status),
    INDEX idx_device_type (device_type),
    INDEX idx_car_no (car_no),
    INDEX idx_atp_type (atp_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='列控设备台账表';

CREATE TABLE phm_risk_result (
    risk_result_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '风险结果ID',
    device_id BIGINT DEFAULT NULL COMMENT '设备主键ID',
    device_code VARCHAR(64) NOT NULL COMMENT '系统设备编号',
    sample_index INT DEFAULT NULL COMMENT '本地窗口样本索引',
    risk_raw DOUBLE DEFAULT NULL COMMENT '模型原始风险概率',
    calibrated_risk_score DOUBLE NOT NULL COMMENT '校准后风险分数',
    risk_std DOUBLE DEFAULT 0 COMMENT '风险分数标准差',
    threshold DOUBLE NOT NULL COMMENT '模型分类阈值',
    predicted_label TINYINT NOT NULL COMMENT '预测标签：0正常，1风险',
    health_score DOUBLE DEFAULT NULL COMMENT '健康度分数',
    health_level VARCHAR(32) DEFAULT NULL COMMENT '健康等级',
    health_status VARCHAR(32) DEFAULT NULL COMMENT '健康状态',
    health_description VARCHAR(255) DEFAULT NULL COMMENT '健康状态描述',
    y_true TINYINT DEFAULT NULL COMMENT '样本真实标签',
    condition_label VARCHAR(64) DEFAULT NULL COMMENT '工况标签',
    ts_end DATETIME DEFAULT NULL COMMENT '请求推理结束时间',
    window_minutes INT DEFAULT NULL COMMENT '请求窗口长度',
    window_start_time DATETIME DEFAULT NULL COMMENT '系统展示窗口开始时间',
    window_end_time DATETIME DEFAULT NULL COMMENT '系统展示窗口结束时间',
    sample_id VARCHAR(128) DEFAULT NULL COMMENT '样本ID',
    segment_id VARCHAR(128) DEFAULT NULL COMMENT '片段ID',
    segment_file VARCHAR(255) DEFAULT NULL COMMENT '片段文件名',
    target_time DATETIME DEFAULT NULL COMMENT '目标行时间',
    target_label_value VARCHAR(128) DEFAULT NULL COMMENT '目标标签值',
    target_alarm_value VARCHAR(128) DEFAULT NULL COMMENT '目标告警值',
    target_atp_type VARCHAR(64) DEFAULT NULL COMMENT '目标行ATP类型',
    target_car_no VARCHAR(64) DEFAULT NULL COMMENT '目标行车号',
    target_train_no VARCHAR(64) DEFAULT NULL COMMENT '目标行车次',
    target_attach_bureau VARCHAR(64) DEFAULT NULL COMMENT '目标行配属铁路局',
    window_start_row INT DEFAULT NULL COMMENT '窗口起始行号',
    window_end_row INT DEFAULT NULL COMMENT '窗口结束行号',
    target_row INT DEFAULT NULL COMMENT '目标行号',
    trace_json JSON DEFAULT NULL COMMENT '完整样本追溯信息',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_device_code_time (device_code, window_end_time),
    INDEX idx_device_id_time (device_id, window_end_time),
    INDEX idx_created_at (created_at),
    INDEX idx_sample_index (sample_index),
    INDEX idx_sample_id (sample_id),
    INDEX idx_segment_id (segment_id),
    INDEX idx_predicted_label (predicted_label),
    INDEX idx_risk_score (calibrated_risk_score),
    INDEX idx_health_level (health_level),

    CONSTRAINT fk_risk_device
        FOREIGN KEY (device_id) REFERENCES phm_device(device_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='故障风险预测结果表';

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

INSERT INTO phm_device (
    device_code,
    device_name,
    device_type,
    device_status,
    atp_type,
    car_no,
    train_no,
    attach_bureau
) VALUES
('ATP001', 'ATP车载设备001', 'ATP', 1, '300S', '3010001', 'G247', '广'),
('ATP002', 'ATP车载设备002', 'ATP', 1, '300T', '3001003', 'C2048', '宁'),
('ATP003', 'ATP车载设备003', 'ATP', 2, '300T', '3001004', 'D1024', '宁');

