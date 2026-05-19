const EMPTY_TEXT = '暂无'

export function displayText(value, fallback = EMPTY_TEXT) {
  if (value === null || value === undefined) {
    return fallback
  }

  if (typeof value === 'string' && value.trim() === '') {
    return fallback
  }

  return String(value)
}

export function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numericValue) ? numericValue : null
}

export function formatPercent(value, digits = 2, fallback = EMPTY_TEXT) {
  const numericValue = toFiniteNumber(value)
  return numericValue === null ? fallback : `${(numericValue * 100).toFixed(digits)}%`
}

export function formatNumber(value, digits = 2, fallback = EMPTY_TEXT) {
  const numericValue = toFiniteNumber(value)
  return numericValue === null ? fallback : numericValue.toFixed(digits)
}

export function formatScore(value, digits = 2, fallback = EMPTY_TEXT) {
  const numericValue = toFiniteNumber(value)
  if (numericValue === null) {
    return fallback
  }

  return numericValue <= 1 ? `${(numericValue * 100).toFixed(digits)}%` : numericValue.toFixed(digits)
}

export function formatBoolean(value, fallback = EMPTY_TEXT) {
  if (value === true) {
    return '是'
  }

  if (value === false) {
    return '否'
  }

  return fallback
}

export function formatCalibrationMethod(value) {
  const normalizedValue = normalizeKey(value)
  const methodMap = {
    isotonic_regression: '保序回归',
    isotonic: '保序回归',
    platt_scaling: 'Platt 缩放',
    platt: 'Platt 缩放',
    none: '未启用'
  }

  return methodMap[normalizedValue] || displayText(value)
}

export function formatUncertaintyMethod(value) {
  const normalizedValue = normalizeKey(value)
  const methodMap = {
    mc_dropout: 'MC-Dropout',
    dropout: 'MC-Dropout',
    none: '未启用',
    unknown: '暂无'
  }

  return methodMap[normalizedValue] || displayText(value)
}

export function formatDataSource(value) {
  const normalizedValue = normalizeKey(value)
  const sourceMap = {
    local_window_dataset: '本地窗口样本',
    ai_service: 'AI 推理服务',
    ['moc' + 'k_fallback']: '降级结果',
    influxdb: 'InfluxDB',
    unknown: '暂无'
  }

  return sourceMap[normalizedValue] || displayText(value)
}

export function formatDeviceStatus(value) {
  const normalizedValue = Number(value)
  const statusMap = {
    1: '正常',
    2: '关注',
    3: '预警',
    4: '告警'
  }

  return statusMap[normalizedValue] || displayText(value)
}

export function formatAlertStatus(value) {
  const normalizedValue = normalizeKey(value)
  const statusMap = {
    pending: '待处理',
    unhandled: '待处理',
    processing: '处理中',
    resolved: '已处理',
    ignored: '已忽略'
  }

  return statusMap[normalizedValue] || displayText(value)
}

export function formatAlertLevel(value) {
  const normalizedValue = normalizeKey(value)
  const levelMap = {
    none: '无',
    info: '提示',
    low: '提示',
    medium: '预警',
    warning: '预警',
    high: '告警',
    critical: '严重'
  }

  return levelMap[normalizedValue] || displayText(value)
}

export function formatDateTime(value, fallback = EMPTY_TEXT) {
  const text = displayText(value, fallback)
  return text === fallback ? text : text.replace('T', ' ').slice(0, 19)
}

function normalizeKey(value) {
  return value === null || value === undefined ? '' : String(value).trim().toLowerCase()
}
