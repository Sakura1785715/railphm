import { toFiniteNumber } from './formatters.js'

export const DEFAULT_EMA_ALPHA = 0.2

export function applyEmaToPoints(points, options = {}) {
  if (!Array.isArray(points) || points.length === 0) {
    return []
  }

  const alpha = normalizeAlpha(options.alpha)
  let previousEma = null

  return points.map((point) => {
    const sourcePoint = point && typeof point === 'object' ? point : { value: point }
    const rawValue = sourcePoint.value
    const numericValue = toFiniteNumber(rawValue)

    if (numericValue === null) {
      return {
        ...sourcePoint,
        value: null,
        rawValue
      }
    }

    const emaValue = previousEma === null ? numericValue : alpha * numericValue + (1 - alpha) * previousEma
    previousEma = emaValue

    return {
      ...sourcePoint,
      value: emaValue,
      rawValue
    }
  })
}

function normalizeAlpha(value) {
  if (typeof value !== 'number' && typeof value !== 'string') {
    return DEFAULT_EMA_ALPHA
  }

  if (typeof value === 'string' && value.trim() === '') {
    return DEFAULT_EMA_ALPHA
  }

  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) {
    return DEFAULT_EMA_ALPHA
  }

  return Math.max(0, Math.min(1, numericValue))
}
