import http from './http'

export function getHealthStatus() {
  return http.get('/v1/health')
}
