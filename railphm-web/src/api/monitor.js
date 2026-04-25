import http from './http'

export function getMonitorSeries(params = {}) {
  return http.get('/v1/monitor/series', { params })
}

