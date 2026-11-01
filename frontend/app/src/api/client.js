import { clearToken, getToken } from '../lib/authStorage'

export class ApiError extends Error {
  constructor(message, { status, data } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

function formatError(data, status) {
  if (!data) return `Ошибка ${status}`
  if (typeof data === 'string') return data
  if (data.detail) {
    return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
  }
  if (data.non_field_errors?.length) return data.non_field_errors.join(', ')
  const parts = []
  for (const [key, val] of Object.entries(data)) {
    if (Array.isArray(val)) parts.push(`${key}: ${val.join(', ')}`)
    else if (typeof val === 'string') parts.push(`${key}: ${val}`)
  }
  return parts.length ? parts.join('; ') : `Ошибка ${status}`
}

export async function api(path, options = {}) {
  const {
    method = 'GET',
    body,
    formData,
    auth = true,
    headers: extraHeaders = {},
  } = options

  const headers = { ...extraHeaders }
  const token = getToken()
  if (auth && token) headers.Authorization = `Token ${token}`

  let payload = body
  if (formData) {
    payload = formData
  } else if (body != null && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const res = await fetch(`/api${path}`, { method, headers, body: payload })

  if (res.status === 204) return null

  const contentType = res.headers.get('content-type') || ''
  const data = contentType.includes('application/json')
    ? await res.json()
    : await res.text()

  if (!res.ok) {
    if (res.status === 401 && auth) clearToken()
    throw new ApiError(formatError(data, res.status), { status: res.status, data })
  }
  return data
}

export function apiDownload(path) {
  const token = getToken()
  return fetch(`/api${path}`, {
    headers: token ? { Authorization: `Token ${token}` } : {},
  })
}
