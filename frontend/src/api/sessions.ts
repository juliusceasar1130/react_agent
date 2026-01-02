import api from './index'
import type { Session, SessionCreate, SessionUpdate } from '@/types'

export const createSessionApi = (data: SessionCreate): Promise<Session> => {
  return api.post('/api/chat/sessions', data)
}

export const getSessionsApi = (): Promise<Session[]> => {
  return api.get('/api/chat/sessions')
}

export const getSessionApi = (id: string): Promise<Session> => {
  return api.get(`/api/chat/sessions/${id}`)
}

export const updateSessionApi = (id: string, data: SessionUpdate): Promise<Session> => {
  return api.put(`/api/chat/sessions/${id}`, data)
}

export const deleteSessionApi = (id: string): Promise<{ message: string }> => {
  return api.delete(`/api/chat/sessions/${id}`)
}
