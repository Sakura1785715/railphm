import http from './http'

export function getDeviceList(params = {}) {
  return http.get('/v1/devices', { params })
}

export function getDeviceDetail(deviceId) {
  return http.get(`/v1/devices/${deviceId}`)
}

export function createDevice(payload) {
  return http.post('/v1/devices', payload)
}

export function updateDevice(deviceId, payload) {
  return http.put(`/v1/devices/${deviceId}`, payload)
}
