import api from './index'
import type { Message, MessageCreate } from '@/types'

export const createMessageApi = (data: MessageCreate): Promise<Message> => {
  return api.post('/api/chat/messages', data)
}

export const getMessageApi = (id: string): Promise<Message> => {
  return api.get(`/api/chat/messages/${id}`)
}

export const getMessagesBySessionApi = (sessionId: string): Promise<Message[]> => {
  return api.get(`/api/chat/sessions/${sessionId}/messages`)
}

export const deleteMessageApi = (id: string): Promise<{ message: string }> => {
  return api.delete(`/api/chat/messages/${id}`)
}
