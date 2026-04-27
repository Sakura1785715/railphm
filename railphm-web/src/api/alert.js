import http from './http'

export function getAlertList(params = {}) {
  return http.get('/v1/alerts', { params })
}

export function getAlertDetail(alertId) {
  return http.get(`/v1/alerts/${alertId}`)
}

export function updateAlertStatus(alertId, payload) {
  return http.patch(`/v1/alerts/${alertId}/status`, payload)
}
