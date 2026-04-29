const EMPTY_TEXT = '--'

const STATUS_MAP = {
  1: { label: '正常', type: 'success' },
  0: { label: '停用', type: 'neutral' },
  NORMAL: { label: '正常', type: 'success' },
  ONLINE: { label: '在线', type: 'success' },
  ACTIVE: { label: '正常', type: 'success' },
  OK: { label: '正常', type: 'success' },
  HEALTHY: { label: '健康', type: 'success' },
  RUNNING: { label: '运行中', type: 'success' },
  SUCCESS: { label: '正常', type: 'success' },
  正常: { label: '正常', type: 'success' },
  在线: { label: '在线', type: 'success' },
  健康: { label: '健康', type: 'success' },
  OFFLINE: { label: '离线', type: 'danger' },
  INACTIVE: { label: '停用', type: 'neutral' },
  ERROR: { label: '异常', type: 'danger' },
  FAILED: { label: '失败', type: 'danger' },
  DANGER: { label: '异常', type: 'danger' },
  离线: { label: '离线', type: 'danger' },
  异常: { label: '异常', type: 'danger' },
  停用: { label: '停用', type: 'neutral' },
  PENDING: { label: '待处理', type: 'warning' },
  PROCESSING: { label: '处理中', type: 'info' },
  RESOLVED: { label: '已解决', type: 'success' },
  待处理: { label: '待处理', type: 'warning' },
  处理中: { label: '处理中', type: 'info' },
  已解决: { label: '已解决', type: 'success' },
  UNKNOWN: { label: '未知', type: 'neutral' }
}

const RISK_MAP = {
  HIGH: { label: '高风险', type: 'danger' },
  MEDIUM: { label: '中风险', type: 'warning' },
  LOW: { label: '低风险', type: 'success' },
  高风险: { label: '高风险', type: 'danger' },
  中风险: { label: '中风险', type: 'warning' },
  低风险: { label: '低风险', type: 'success' },
  UNKNOWN: { label: '未知', type: 'neutral' }
}

export function normalizeDisplayValue(value, emptyText = EMPTY_TEXT) {
  if (value === null || value === undefined || value === '') {
    return emptyText
  }

  return String(value)
}

export function resolveStatusMeta(value, type = '', label = '') {
  const explicitType = normalizeTone(type)
  const normalizedValue = normalizeKey(value)
  const mapped = STATUS_MAP[normalizedValue]

  return {
    label: label || mapped?.label || normalizeDisplayValue(value, '未知'),
    type: explicitType || mapped?.type || 'neutral'
  }
}

export function resolveRiskMeta(level, score) {
  const normalizedLevel = normalizeKey(level)
  const inferredLevel = normalizedLevel || inferRiskLevel(score)
  const mapped = RISK_MAP[inferredLevel] || RISK_MAP.UNKNOWN

  return {
    level: inferredLevel || 'UNKNOWN',
    label: mapped.label,
    type: mapped.type
  }
}

export function resolveHealthMeta(score) {
  const normalizedScore = toFiniteNumber(score)

  if (normalizedScore === null) {
    return {
      label: '暂无健康度',
      type: 'neutral',
      score: null,
      valueText: '暂无健康度'
    }
  }

  if (normalizedScore <= 30) {
    return {
      label: '危险',
      type: 'danger',
      score: normalizedScore,
      valueText: normalizedScore.toFixed(1)
    }
  }

  if (normalizedScore < 70) {
    return {
      label: '关注',
      type: 'warning',
      score: normalizedScore,
      valueText: normalizedScore.toFixed(1)
    }
  }

  return {
    label: '健康',
    type: 'success',
    score: normalizedScore,
    valueText: normalizedScore.toFixed(1)
  }
}

export function normalizeTone(type) {
  const normalizedType = normalizeKey(type).toLowerCase()
  return ['default', 'primary', 'success', 'warning', 'danger', 'info', 'neutral', 'muted'].includes(normalizedType)
    ? normalizedType
    : ''
}

export function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numericValue) ? numericValue : null
}

function normalizeKey(value) {
  if (value === null || value === undefined || value === '') {
    return ''
  }

  return String(value).trim().toUpperCase()
}

function inferRiskLevel(score) {
  const normalizedScore = toFiniteNumber(score)

  if (normalizedScore === null) {
    return 'UNKNOWN'
  }

  if (normalizedScore >= 0.7) {
    return 'HIGH'
  }

  if (normalizedScore >= 0.3) {
    return 'MEDIUM'
  }

  return 'LOW'
}
