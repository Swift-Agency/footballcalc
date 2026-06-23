import { ref } from 'vue'
import { pollPayment } from '../api'
import { refreshBillingProfile } from './useBillingProfile'

const STORAGE_KEY = 'fc_pending_payment'
const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 120_000

export type PaymentPollPhase = 'idle' | 'polling' | 'success' | 'failed' | 'timeout'

export const paymentPollPhase = ref<PaymentPollPhase>('idle')
export const paymentPollMessage = ref('')

let pollRunning = false

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export function savePendingPayment(paymentId: number): void {
  sessionStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ paymentId, startedAt: Date.now() }),
  )
}

export function clearPendingPayment(): void {
  sessionStorage.removeItem(STORAGE_KEY)
}

export function getPendingPaymentId(): number | null {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    const data = JSON.parse(raw) as { paymentId?: number }
    return typeof data.paymentId === 'number' ? data.paymentId : null
  } catch {
    return null
  }
}

export function notifyBillingUpdated(): void {
  window.dispatchEvent(new CustomEvent('billing-updated'))
}

async function pollUntilDone(paymentId: number): Promise<PaymentPollPhase> {
  const deadline = Date.now() + POLL_TIMEOUT_MS
  while (Date.now() < deadline) {
    const { status } = await pollPayment(paymentId)
    if (status === 'succeeded') return 'success'
    if (status === 'canceled' || status === 'failed') return 'failed'
    await sleep(POLL_INTERVAL_MS)
  }
  return 'timeout'
}

export async function resumePendingPayment(forcePaymentId?: number): Promise<PaymentPollPhase | null> {
  const paymentId = forcePaymentId ?? getPendingPaymentId()
  if (!paymentId || pollRunning) return null

  pollRunning = true
  paymentPollPhase.value = 'polling'
  paymentPollMessage.value = 'Проверяем оплату...'

  try {
    const result = await pollUntilDone(paymentId)
    paymentPollPhase.value = result

    if (result === 'success') {
      clearPendingPayment()
      await refreshBillingProfile()
      notifyBillingUpdated()
      paymentPollMessage.value = 'Оплата прошла успешно!'
      await sleep(1500)
      paymentPollPhase.value = 'idle'
      return result
    }

    if (result === 'failed') {
      clearPendingPayment()
      paymentPollMessage.value = 'Оплата не завершена. Попробуйте снова.'
      await sleep(2500)
      paymentPollPhase.value = 'idle'
      return result
    }

    paymentPollMessage.value =
      'Подтверждение задерживается. Статус обновится через минуту — потяните экран вниз или зайдите в «Подписка».'
    await sleep(3500)
    paymentPollPhase.value = 'idle'
    return result
  } catch (err) {
    console.error('[PaymentPoll] error:', err)
    paymentPollPhase.value = 'idle'
    return null
  } finally {
    pollRunning = false
  }
}

export function checkoutReturnUrl(): string {
  const base = window.location.origin
  return `${base}/info/subscription`
}
