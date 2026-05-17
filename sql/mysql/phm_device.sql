CREATE DATABASE IF NOT EXISTS railphm
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE railphm;

DROP TABLE IF EXISTS phm_device;

CREATE TABLE phm_device (
    device_id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '设备ID',
    device_code VARCHAR(64) NOT NULL UNIQUE COMMENT '系统设备编号',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称',
    device_type VARCHAR(64) NOT NULL DEFAULT 'ATP' COMMENT '设备类型',

    device_status TINYINT NOT NULL DEFAULT 1 COMMENT '设备状态：1正常，2关注，3预警，4告警',

    atp_type VARCHAR(64) DEFAULT NULL COMMENT 'ATP类型',
    car_no VARCHAR(64) DEFAULT NULL COMMENT '车号',
    train_no VARCHAR(64) DEFAULT NULL COMMENT '车次',
    attach_bureau VARCHAR(64) DEFAULT NULL COMMENT '配属铁路局',

    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_device_code (device_code),
    INDEX idx_device_status (device_status),
    INDEX idx_device_type (device_type),
    INDEX idx_car_no (car_no),
    INDEX idx_atp_type (atp_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='列控设备台账表';

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