import { api } from './api'

let pendingSave: Promise<unknown> = Promise.resolve()

/** Merge only the caller's fields into the latest settings, in page-local order. */
export function saveClientSettings<T>(changes: Record<string, unknown>): Promise<T> {
  const snapshot = JSON.parse(JSON.stringify(changes)) as Record<string, unknown>
  const task = pendingSave.then(async () => {
    const current = await api<{settings: Record<string, unknown>}>('/api/client/settings')
    return api<T>('/api/client/settings', 'PUT', {...current.settings, ...snapshot})
  })
  pendingSave = task.catch(() => undefined)
  return task
}
