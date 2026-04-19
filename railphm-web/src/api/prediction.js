import http from './http'

export function getLatestPrediction(deviceId) {
  return http.get('/v1/predictions/latest', {
    params: {
      device_id: deviceId
    }
  })
}

export function getPredictionHistory(params = {}) {
  return http.get('/v1/predictions/history', { params })
}
