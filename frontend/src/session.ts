import { v4 as uuidv4 } from 'uuid'

const SESSION_KEY = 'analyst_session_id'
const USER_KEY    = 'analyst_user_id'
const CONN_KEY    = 'analyst_connector_id'

export function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY)
  if (!id) { id = uuidv4(); localStorage.setItem(SESSION_KEY, id) }
  return id
}

export function newSession(): string {
  const id = uuidv4()
  localStorage.setItem(SESSION_KEY, id)
  return id
}

export function getUserId(): string {
  let id = localStorage.getItem(USER_KEY)
  if (!id) { id = uuidv4(); localStorage.setItem(USER_KEY, id) }
  return id
}

export function getConnectorId(): string {
  return localStorage.getItem(CONN_KEY) || 'neon:public'
}

export function setConnectorId(id: string): void {
  localStorage.setItem(CONN_KEY, id)
}
