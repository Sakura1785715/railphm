CREATE TABLE phm_run_record (
  run_record_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  run_record_code VARCHAR(128) NOT NULL UNIQUE,

  device_id BIGINT NULL,
  device_code VARCHAR(64) NOT NULL,

  source_segment VARCHAR(255) NOT NULL,
  source_file VARCHAR(255) NULL,

  record_start_time DATETIME NOT NULL,
  record_end_time DATETIME NOT NULL,
  source_start_time DATETIME NULL,
  source_end_time DATETIME NULL,

  point_count INT NOT NULL DEFAULT 0,
  duration_seconds INT NULL,

  atp_type VARCHAR(64) NULL,
  line_id VARCHAR(64) NULL,
  direction VARCHAR(32) NULL,

  condition_summary JSON NULL,
  has_alarm_label TINYINT NOT NULL DEFAULT 0,

  status VARCHAR(32) NOT NULL DEFAULT 'ready',

  max_risk_score DOUBLE NULL,
  max_risk_result_id BIGINT NULL,
  max_alert_level VARCHAR(32) NULL,
  alert_id BIGINT NULL,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_run_record_device_segment (device_code, source_segment),
  KEY idx_run_record_device_time (device_code, record_start_time),
  KEY idx_run_record_status (status),
  KEY idx_run_record_risk (max_risk_score)
);