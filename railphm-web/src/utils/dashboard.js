export function formatDecimal(value, digits = 2, fallback = '--') {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : fallback
}

export function formatCount(value, fallback = '--') {
  return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('zh-CN') : fallback
}

export function formatDateTime(value, fallback = '未返回') {
  if (!value) {
    return fallback
  }

  const normalizedValue =
    value instanceof Date ? value : String(value).replace(' ', 'T')

  const date = new Date(normalizedValue)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

export function formatWindowRange(start, end) {
  if (!start && !end) {
    return '未返回'
  }

  return `${formatDateTime(start)} - ${formatDateTime(end)}`
}

export function formatModelVersion(version) {
  if (!version) {
    return '未返回'
  }

  return version.length > 18 ? `${version.slice(0, 18)}...` : version
}

export function getServiceStatusMeta(status) {
  if (status === 'running') {
    return {
      label: '系统在线',
      badge: '服务可用',
      tone: 'success',
      description: '健康检查接口返回运行中'
    }
  }

  return {
    label: status || '状态未知',
    badge: '待确认',
    tone: 'warning',
    description: '健康检查接口未返回稳定运行标识'
  }
}

export function getDeviceStatusMeta(deviceStatus) {
  if (deviceStatus === 1) {
    return {
      label: '在册运行',
      tone: 'success'
    }
  }

  if (deviceStatus === 0) {
    return {
      label: '停用观察',
      tone: 'warning'
    }
  }

  return {
    label: '状态未知',
    tone: 'muted'
  }
}

export function getRiskLevelMeta(healthScore) {
  if (typeof healthScore !== 'number' || !Number.isFinite(healthScore)) {
    return {
      label: '结果已更新',
      tone: 'muted',
      description: '等待健康度结果解释'
    }
  }

  if (healthScore <= 30) {
    return {
      label: '高风险',
      tone: 'danger',
      description: '建议尽快复核设备状态'
    }
  }

  if (healthScore <= 70) {
    return {
      label: '需关注',
      tone: 'warning',
      description: '建议结合监测数据持续跟踪'
    }
  }

  return {
    label: '状态良好',
    tone: 'success',
    description: '健康度处于稳定区间'
  }
}

export function getHealthStatusMeta(healthScore) {
  if (typeof healthScore !== 'number' || !Number.isFinite(healthScore)) {
    return {
      label: '待评估',
      tone: 'muted'
    }
  }

  if (healthScore <= 30) {
    return {
      label: '健康告警',
      tone: 'danger'
    }
  }

  if (healthScore <= 70) {
    return {
      label: '重点关注',
      tone: 'warning'
    }
  }

  return {
    label: '健康稳定',
    tone: 'success'
  }
}

export function toRiskProgress(riskScore) {
  if (typeof riskScore !== 'number' || !Number.isFinite(riskScore)) {
    return 0
  }

  return Math.max(0, Math.min(100, riskScore * 100))
}

export function toHealthProgress(healthScore) {
  if (typeof healthScore !== 'number' || !Number.isFinite(healthScore)) {
    return 0
  }

  return Math.max(0, Math.min(100, healthScore))
}
