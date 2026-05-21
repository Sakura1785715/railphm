import http from './http'

const RANGE_INFER_MIN_TIMEOUT_MS = 30000
const RANGE_INFER_MAX_TIMEOUT_MS = 180000
const RANGE_INFER_PER_POINT_TIMEOUT_MS = 1500

export function getLatestPrediction(params = {}) {
  const normalizedParams =
    params && typeof params === 'object'
      ? params
      : {
          device_id: params
        }

  return http.get('/v1/predictions/latest', {
    params: normalizedParams
  })
}

export function getPredictionHistory(params = {}) {
  return http.get('/v1/predictions/history', { params })
}

export function getHealthCurve(params = {}) {
  return http.get('/v1/predictions/health-curve', { params })
}

export function inferPrediction(payload = {}) {
  return http.post('/v1/predictions/infer', payload)
}

export function inferPredictionRange(payload = {}) {
  return http.post('/v1/predictions/range-infer', payload, {
    timeout: buildRangeInferTimeout(payload)
  })
}

function buildRangeInferTimeout(payload = {}) {
  const lookbackMinutes = Number(payload.lookback_minutes)
  const strideSeconds = Number(payload.inference_stride_seconds)

  if (!Number.isFinite(lookbackMinutes) || !Number.isFinite(strideSeconds) || strideSeconds <= 0) {
    return RANGE_INFER_MAX_TIMEOUT_MS
  }

  const candidatePoints = Math.floor((lookbackMinutes * 60) / strideSeconds) + 1
  const estimatedTimeout = candidatePoints * RANGE_INFER_PER_POINT_TIMEOUT_MS
  return Math.max(
    RANGE_INFER_MIN_TIMEOUT_MS,
    Math.min(RANGE_INFER_MAX_TIMEOUT_MS, estimatedTimeout)
  )
}
