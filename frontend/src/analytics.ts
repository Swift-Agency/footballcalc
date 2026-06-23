import { getTelegram } from './telegram'

const _isLocalhost =
  typeof window !== 'undefined' && /localhost|127\.0\.0\.1/.test(window.location.host)

const API_BASE: string =
  import.meta.env.VITE_API_URL ||
  (_isLocalhost
    ? import.meta.env.DEV
      ? '/api'
      : 'http://localhost:8000/api'
    : '/api')

let _seq = 0

export function postAppEvent(
  eventType: string,
  payload?: Record<string, unknown>,
  telegramUserId?: number,
): void {
  const secret = import.meta.env.VITE_EVENTS_SECRET as string | undefined
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (secret) headers['X-Event-Secret'] = secret
  const initData = getTelegram()?.initData
  if (initData) headers['X-Telegram-Init-Data'] = initData
  const body = JSON.stringify({
    event_type: eventType,
    payload: payload ? { ...payload, _seq: ++_seq } : { _seq: ++_seq },
    telegram_user_id: telegramUserId,
  })
  void fetch(`${API_BASE}/events`, { method: 'POST', headers, body }).catch(() => {})
}
