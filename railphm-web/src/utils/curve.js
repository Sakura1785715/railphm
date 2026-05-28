import { toFiniteNumber } from './formatters'

export const DISPLAY_SMOOTH_ALPHA = 0.08

export function buildRiskHealthCurve(records = [], options = {}) {
  if (!Array.isArray(records) || records.length === 0) {
    return []
  }

  const {
    alpha = DISPLAY_SMOOTH_ALPHA,
    timeGetter = (item) => item?.time || item?.window_end_time || item?.ts_end || item?.created_at || '',
    riskGetter = (item) => item?.risk_score,
    healthGetter = (item) => item?.health_score
  } = options

  const sortedRecords = records
    .map((item, index) => ({
      item,
      index,
      time: timeGetter(item) || ''
    }))
    .sort((a, b) => {
      const timeCompare = String(a.time).localeCompare(String(b.time))
      return timeCompare === 0 ? a.index - b.index : timeCompare
    })

  let previousSmoothedRisk = null

  return sortedRecords
    .map(({ item, time }) => {
      const riskScoreRaw = clipRiskScore(riskGetter(item))
      if (riskScoreRaw === null) {
        return null
      }

      const riskScoreSmoothed =
        previousSmoothedRisk === null
          ? riskScoreRaw
          : alpha * riskScoreRaw + (1 - alpha) * previousSmoothedRisk
      previousSmoothedRisk = riskScoreSmoothed

      return {
        ...item,
        time,
        risk_score_raw: roundNumber(riskScoreRaw, 6),
        risk_score_smoothed: roundNumber(riskScoreSmoothed, 6),
        health_score_raw: resolveHealthScore(healthGetter(item), riskScoreRaw),
        health_score_smoothed: roundNumber(100 * (1 - riskScoreSmoothed), 2)
      }
    })
    .filter(Boolean)
}

export function clipRiskScore(value) {
  const numericValue = toFiniteNumber(value)
  if (numericValue === null) {
    return null
  }

  return Math.max(0, Math.min(1, numericValue))
}

export function roundNumber(value, decimals) {
  const numericValue = toFiniteNumber(value)
  if (numericValue === null) {
    return null
  }

  const factor = 10 ** decimals
  return Math.round(numericValue * factor) / factor
}

function resolveHealthScore(value, riskScoreRaw) {
  const healthScore = toFiniteNumber(value)
  if (healthScore !== null) {
    return roundNumber(healthScore, 2)
  }

  return roundNumber(100 * (1 - riskScoreRaw), 2)
}
