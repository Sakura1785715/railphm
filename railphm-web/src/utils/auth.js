const TOKEN_KEY = 'railphm_token'
const USER_KEY = 'railphm_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function getStoredUser() {
  const rawUser = localStorage.getItem(USER_KEY)

  if (!rawUser) {
    return null
  }

  try {
    return JSON.parse(rawUser)
  } catch {
    removeStoredUser()
    return null
  }
}

export function setStoredUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function removeStoredUser() {
  localStorage.removeItem(USER_KEY)
}

export function clearAuth() {
  removeToken()
  removeStoredUser()
}

export function isLoggedIn() {
  return Boolean(getToken())
}

export function getStoredRole() {
  return getStoredUser()?.role || ''
}

export function isAdmin() {
  return getStoredRole() === 'ADMIN'
}

export function isOps() {
  return getStoredRole() === 'OPS'
}

export function hasAnyRole(roles = []) {
  return roles.includes(getStoredRole())
}
