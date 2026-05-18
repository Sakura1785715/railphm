import http from './http'

export function getDashboardOverview() {
  return http.get('/v1/dashboard/overview')
}
