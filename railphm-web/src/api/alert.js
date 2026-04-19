import http from './http'

export function getAlertList(params = {}) {
  return http.get('/v1/alerts', { params })
}
