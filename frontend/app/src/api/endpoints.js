import { api, apiDownload } from './client'

export const authApi = {
  login: (email, password) =>
    api('/auth/token/', { method: 'POST', body: { email, password }, auth: false }),
  logout: () => api('/auth/logout/', { method: 'POST' }),
}

export const activitiesApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return api(`/activities/${q ? `?${q}` : ''}`)
  },
  get: (id) => api(`/activities/${id}/`),
  create: (formData) => api('/activities/', { method: 'POST', formData }),
  update: (id, body) => api(`/activities/${id}/`, { method: 'PATCH', body }),
  remove: (id) => api(`/activities/${id}/`, { method: 'DELETE' }),
  react: (id, emoji) => api(`/activities/${id}/react/`, { method: 'POST', body: { emoji } }),
  comments: {
    listCreate: (id, text) =>
      text
        ? api(`/activities/${id}/comments/`, { method: 'POST', body: { text } })
        : api(`/activities/${id}/comments/`),
    update: (id, commentId, text) =>
      api(`/activities/${id}/comments/${commentId}/`, { method: 'PATCH', body: { text } }),
    remove: (id, commentId) =>
      api(`/activities/${id}/comments/${commentId}/`, { method: 'DELETE' }),
  },
  download: (id) => apiDownload(`/activities/${id}/download/`),
}

export const activityTypesApi = {
  list: () => api('/activity-types/'),
}

export const leadersApi = {
  weekly: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return api(`/leaders/weekly/${q ? `?${q}` : ''}`)
  },
}

export const peopleApi = {
  search: (q) => api(`/people/search/?q=${encodeURIComponent(q || '')}`),
  requests: () => api('/people/requests/'),
  accept: (id) => api(`/people/requests/${id}/accept/`, { method: 'POST' }),
  reject: (id) => api(`/people/requests/${id}/reject/`, { method: 'POST' }),
  profile: (id) => api(`/people/${id}/`),
  following: (id) => api(`/people/${id}/following/`),
  followers: (id) => api(`/people/${id}/followers/`),
  follow: (id) => api(`/people/${id}/follow/`, { method: 'POST' }),
  removeFollower: (id) => api(`/people/${id}/remove-follower/`, { method: 'POST' }),
}

export const meApi = {
  get: () => api('/me/'),
  update: (bodyOrForm) => {
    if (bodyOrForm instanceof FormData) {
      return api('/me/', { method: 'PATCH', formData: bodyOrForm })
    }
    return api('/me/', { method: 'PATCH', body: bodyOrForm })
  },
  password: (body) => api('/me/password/', { method: 'POST', body }),
  deleteAccount: (body) => api('/me/delete/', { method: 'POST', body }),
  intervalsConnect: (body) =>
    api('/me/integrations/intervals/connect/', { method: 'POST', body }),
  intervalsDisconnect: () =>
    api('/me/integrations/intervals/disconnect/', { method: 'POST' }),
  garminConnect: (body) =>
    api('/me/integrations/garmin/connect/', { method: 'POST', body }),
  garminDisconnect: () =>
    api('/me/integrations/garmin/disconnect/', { method: 'POST' }),
  garminSyncZones: () =>
    api('/me/integrations/garmin/sync-power-zones/', { method: 'POST' }),
}

export const routesApi = {
  list: (params = {}) => {
    // Backend expects `tab` (mine|following|public)
    const q = new URLSearchParams(params).toString()
    return api(`/routes/${q ? `?${q}` : ''}`)
  },
  get: (id) => api(`/routes/${id}/`),
  create: (formData) => api('/routes/', { method: 'POST', formData }),
  update: (id, body) => api(`/routes/${id}/`, { method: 'PATCH', body }),
  remove: (id) => api(`/routes/${id}/`, { method: 'DELETE' }),
  fromActivity: (activityId, body) =>
    api(`/routes/from-activity/${activityId}/`, { method: 'POST', body }),
  gpx: (id) => apiDownload(`/routes/${id}/gpx/`),
}
