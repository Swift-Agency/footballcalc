import { computed, reactive } from 'vue'
import {
  getBillingConfig,
  getBillingMe,
  getReferralStats,
  isLegalAcceptanceRequired,
  type BillingConfig,
  type BillingMeResponse,
  type ReferralStats,
} from '../api'

const state = reactive({
  me: null as BillingMeResponse | null,
  config: null as BillingConfig | null,
  referralStats: null as ReferralStats | null,
  defaultLimit: 5,
  loaded: false,
  loading: false,
  legalBlocked: false,
})

let loadPromise: Promise<void> | null = null

export function buildReferralLink(
  me: BillingMeResponse | null,
  botUsername: string | null | undefined,
): string | null {
  if (me?.referral_link) return me.referral_link
  const code = me?.referral_code
  const bot = botUsername?.replace(/^@/, '')
  if (!code || !bot) return null
  return `https://t.me/${bot}/?startapp=${code}`
}

export async function refreshBillingProfile(): Promise<void> {
  state.loading = true
  state.legalBlocked = false
  try {
    let meResp = await getBillingMe().catch((err) => {
      if (isLegalAcceptanceRequired(err)) {
        state.legalBlocked = true
      }
      return null
    })
    if (!meResp) {
      await new Promise((resolve) => setTimeout(resolve, 250))
      meResp = await getBillingMe().catch((err) => {
        if (isLegalAcceptanceRequired(err)) {
          state.legalBlocked = true
        }
        return null
      })
    }

    const cfg = await getBillingConfig().catch(() => null)
    const stats = meResp ? await getReferralStats().catch(() => null) : null

    state.me = meResp
    state.config = cfg
    state.referralStats = stats
    if (cfg?.weekly_free_quota) {
      state.defaultLimit = cfg.weekly_free_quota
    }
    state.loaded = true
  } finally {
    state.loading = false
  }
}

export function ensureBillingProfileLoaded(): Promise<void> {
  if (state.loaded && state.me && !loadPromise) {
    return Promise.resolve()
  }
  if (!loadPromise) {
    loadPromise = refreshBillingProfile().finally(() => {
      loadPromise = null
    })
  }
  return loadPromise
}

/** @deprecated use refreshBillingProfile */
export async function refreshQuotaStatus(): Promise<void> {
  await refreshBillingProfile()
}

/** @deprecated use ensureBillingProfileLoaded */
export function ensureQuotaStatusLoaded(): Promise<void> {
  return ensureBillingProfileLoaded()
}

export function useBillingProfile() {
  const isUnlimited = computed(() => state.me?.is_unlimited ?? false)
  const isSubscribed = computed(() => state.me?.is_subscribed ?? false)
  const remaining = computed(() => state.me?.quota?.remaining ?? state.defaultLimit)
  const weeklyLimit = computed(() => state.me?.quota?.weekly_limit ?? state.defaultLimit)
  const used = computed(() => state.me?.quota?.used ?? 0)
  const percentUsed = computed(() => {
    const limit = weeklyLimit.value
    if (!limit) return 0
    return Math.round((used.value / limit) * 100)
  })
  const referralLink = computed(() =>
    buildReferralLink(state.me, state.config?.bot_username),
  )
  const hasDiscount = computed(() => state.me?.has_discount ?? false)
  const discountExpiresAt = computed(() => state.me?.discount_expires_at ?? null)
  const regularPrice = computed(() => Math.round(state.config?.price_rub ?? 0))
  const discountPrice = computed(() => Math.round(state.config?.discount_price_rub ?? 0))
  const loaded = computed(() => state.loaded)
  const loading = computed(() => state.loading)
  const legalBlocked = computed(() => state.legalBlocked)

  return {
    state,
    loaded,
    loading,
    legalBlocked,
    isUnlimited,
    isSubscribed,
    remaining,
    weeklyLimit,
    used,
    percentUsed,
    referralLink,
    hasDiscount,
    discountExpiresAt,
    regularPrice,
    discountPrice,
    refresh: refreshBillingProfile,
    ensureLoaded: ensureBillingProfileLoaded,
  }
}

export function useQuotaStatus() {
  const profile = useBillingProfile()
  return {
    state: profile.state,
    loaded: profile.loaded,
    isUnlimited: profile.isUnlimited,
    remaining: profile.remaining,
    weeklyLimit: profile.weeklyLimit,
    used: profile.used,
    percentUsed: profile.percentUsed,
    hasDiscount: profile.hasDiscount,
    discountExpiresAt: profile.discountExpiresAt,
    regularPrice: profile.regularPrice,
    discountPrice: profile.discountPrice,
    refresh: profile.refresh,
    ensureLoaded: profile.ensureLoaded,
  }
}
