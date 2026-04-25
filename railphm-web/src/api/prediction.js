import http from './http'

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

export function inferPrediction(payload = {}) {
  return http.post('/v1/predictions/infer', payload)
}
