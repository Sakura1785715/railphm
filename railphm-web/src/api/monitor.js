import http from './http'

export function getMonitorSeries(params = {}) {
  return http.get('/v1/monitor/series', { params })
}

export function getMonitorHistory(params = {}) {
  return http.get('/v1/monitor/history', { params })
}
