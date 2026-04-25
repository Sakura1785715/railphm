import http from './http'

export function getDeviceList(params = {}) {
  return http.get('/v1/devices', { params })
}

export function getDeviceDetail(deviceId) {
  return http.get(`/v1/devices/${deviceId}`)
}
