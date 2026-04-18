-- ==========================================================
-- RailPHM MySQL 核心业务表 DDL 初始化脚本
-- 依据《高铁列控设备故障预测与健康管理系统》论文需求文档设计
-- 注意：监控点表 (phm_monitor_data) 归属 InfluxDB，不在此脚本内
-- ==========================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0; -- 临时关闭外键检查，方便重复执行 DROP

-- 1. 逆序清理已存在的表（根据外键依赖关系）
DROP TABLE IF EXISTS `phm_alert_record`;
DROP TABLE IF EXISTS `phm_risk_result`;
DROP TABLE IF EXISTS `phm_monitor_segment`;
DROP TABLE IF EXISTS `phm_maintenance_record`;
DROP TABLE IF EXISTS `phm_user`;
DROP TABLE IF EXISTS `phm_device`;

-- 2. 创建 ATP 设备表
CREATE TABLE `phm_device` (
    `device_id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '设备ID',
    `car_no` VARCHAR(20) DEFAULT NULL COMMENT '车号',
    `atp_type` VARCHAR(20) DEFAULT NULL COMMENT 'ATP类型',
    `attach_bureau` VARCHAR(20) DEFAULT NULL COMMENT '配属铁路局',
    `device_status` TINYINT(1) DEFAULT NULL COMMENT '设备状态',
    PRIMARY KEY (`device_id`),
    KEY `idx_car_no` (`car_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ATP设备表';

-- 3. 创建 系统用户表
CREATE TABLE `phm_user` (
    `user_id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `username` VARCHAR(32) NOT NULL COMMENT '用户名',
    `password_hash` VARCHAR(64) NOT NULL COMMENT '密码哈希',
    `real_name` VARCHAR(20) DEFAULT NULL COMMENT '姓名',
    `role_type` VARCHAR(20) DEFAULT NULL COMMENT '角色类型',
    `phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号',
    `enabled` TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    PRIMARY KEY (`user_id`),
    UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- 4. 创建 检修台账表
CREATE TABLE `phm_maintenance_record` (
    `maint_id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '检修ID',
    `device_id` INT(11) NOT NULL COMMENT '设备ID',
    `maint_type` VARCHAR(20) DEFAULT NULL COMMENT '检修类型',
    `maint_component` VARCHAR(50) DEFAULT NULL COMMENT '检修部件',
    `maint_result` VARCHAR(100) DEFAULT NULL COMMENT '检修结果',
    PRIMARY KEY (`maint_id`),
    KEY `idx_device_id` (`device_id`),
    CONSTRAINT `fk_maint_device` FOREIGN KEY (`device_id`) REFERENCES `phm_device` (`device_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检修台账表';

-- 5. 创建 连续监测片段表
CREATE TABLE `phm_monitor_segment` (
    `segment_id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '片段ID',
    `device_id` INT(11) NOT NULL COMMENT '设备ID',
    `train_no` VARCHAR(20) DEFAULT NULL COMMENT '车次',
    `via_bureau` VARCHAR(50) DEFAULT NULL COMMENT '途经铁路局',
    `cross_day_flag` TINYINT(1) DEFAULT NULL COMMENT '是否跨天',
    `main_driver_id` VARCHAR(20) DEFAULT NULL COMMENT '主司机号',
    `vice_driver_id` VARCHAR(20) DEFAULT NULL COMMENT '副司机号',
    `run_direction` INT(2) DEFAULT NULL COMMENT '运行方向',
    `start_time` DATETIME DEFAULT NULL COMMENT '开始时间',
    `end_time` DATETIME DEFAULT NULL COMMENT '结束时间',
    `segment_length` INT(11) DEFAULT NULL COMMENT '片段长度',
    `point_count` INT(11) DEFAULT NULL COMMENT '数据点数',
    PRIMARY KEY (`segment_id`),
    KEY `idx_device_id` (`device_id`),
    KEY `idx_device_start` (`device_id`, `start_time`),
    CONSTRAINT `fk_segment_device` FOREIGN KEY (`device_id`) REFERENCES `phm_device` (`device_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='连续监测片段表';

-- 6. 创建 风险评估结果表
CREATE TABLE `phm_risk_result` (
    `risk_result_id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '风险结果ID',
    `segment_id` INT(11) NOT NULL COMMENT '片段ID',
    `window_start_time` DATETIME DEFAULT NULL COMMENT '窗口开始时间',
    `window_end_time` DATETIME DEFAULT NULL COMMENT '窗口结束时间',
    `condition_label` VARCHAR(32) DEFAULT NULL COMMENT '工况标签',
    `model_version` VARCHAR(32) DEFAULT NULL COMMENT '模型版本',
    `raw_score` DECIMAL(8,4) DEFAULT NULL COMMENT '原始分数',
    `calibrated_risk_score` DECIMAL(8,4) DEFAULT NULL COMMENT '校准后风险分数',
    `risk_std` DECIMAL(8,4) DEFAULT NULL COMMENT '风险标准差',
    `health_score` DECIMAL(8,4) DEFAULT NULL COMMENT '健康度(最小工程补充)',
    PRIMARY KEY (`risk_result_id`),
    KEY `idx_segment_id` (`segment_id`),
    KEY `idx_segment_window` (`segment_id`, `window_start_time`),
    CONSTRAINT `fk_risk_segment` FOREIGN KEY (`segment_id`) REFERENCES `phm_monitor_segment` (`segment_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险评估结果表';

-- 7. 创建 告警记录表
CREATE TABLE `phm_alert_record` (
    `alert_id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '告警ID',
    `handler_id` INT(11) DEFAULT NULL COMMENT '处理人ID',
    `risk_result_id` INT(11) NOT NULL COMMENT '风险结果ID', -- 【已根据建议修正为 NOT NULL】
    `alert_level` VARCHAR(16) DEFAULT NULL COMMENT '告警级别',
    `alert_source` VARCHAR(32) DEFAULT NULL COMMENT '告警来源',
    `alert_position` VARCHAR(50) DEFAULT NULL COMMENT '告警部位',
    `alert_object_type` VARCHAR(32) DEFAULT NULL COMMENT '告警对象类型',
    `alert_object_code` VARCHAR(32) DEFAULT NULL COMMENT '告警对象编码',
    `alert_status` VARCHAR(16) DEFAULT NULL COMMENT '告警状态',
    `alert_time` DATETIME DEFAULT NULL COMMENT '告警时间',
    `handle_time` DATETIME DEFAULT NULL COMMENT '处理时间',
    `handle_desc` VARCHAR(255) DEFAULT NULL COMMENT '处理说明',
    PRIMARY KEY (`alert_id`),
    KEY `idx_handler_id` (`handler_id`),
    KEY `idx_risk_result_id` (`risk_result_id`),
    KEY `idx_alert_time` (`alert_time`),
    KEY `idx_alert_status` (`alert_status`),
    CONSTRAINT `fk_alert_handler` FOREIGN KEY (`handler_id`) REFERENCES `phm_user` (`user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_alert_risk` FOREIGN KEY (`risk_result_id`) REFERENCES `phm_risk_result` (`risk_result_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警记录表';

SET FOREIGN_KEY_CHECKS = 1; -- 恢复外键检查