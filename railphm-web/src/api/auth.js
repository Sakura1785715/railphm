import http from './http'

export function login(payload) {
  return http.post('/v1/auth/login', payload)
}

export function getCaptcha() {
  return http.get('/v1/auth/captcha')
}

export function getCurrentUser() {
  return http.get('/v1/auth/me')
}

export function logout() {
  return http.post('/v1/auth/logout')
}
