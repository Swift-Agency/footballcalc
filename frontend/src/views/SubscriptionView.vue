<template>
  <div class="page sub-page">
    <div class="leagues-page-header">
      <div class="leagues-page-header-inner">
        <h1>Подписка</h1>
      </div>
    </div>

    <div class="sub-content">
      <div v-if="loading" class="loading">Загрузка...</div>

      <template v-else>
        <!-- Quota card (always shown) -->
        <div class="quota-card">
          <div class="quota-card-row">
            <span class="quota-label">Бесплатных запросов в неделю</span>
            <span class="quota-value">
              <template v-if="me?.is_unlimited">♾ Безлимит</template>
              <template v-else>{{ me?.quota?.remaining ?? 0 }} из {{ me?.quota?.weekly_limit ?? 5 }}</template>
            </span>
          </div>
          <div v-if="me?.quota && !me.is_unlimited" class="quota-bar">
            <div
              class="quota-bar-fill"
              :style="{ width: `${quotaPercent}%` }"
            ></div>
          </div>
          <div v-if="me?.quota?.resets_at && !me.is_unlimited" class="quota-reset">
            Обновление {{ formatDate(me.quota.resets_at) }}
          </div>
        </div>

        <!-- No subscription -->
        <div v-if="!subInfo" class="sub-card">
          <div class="sub-icon">🔓</div>
          <h2 class="sub-title">Нет активной подписки</h2>
          <p class="sub-desc">Оформите подписку, чтобы получить безлимитный доступ к xG и калькулятору.</p>

          <!-- Discount banner if eligible -->
          <div v-if="me?.has_discount" class="discount-banner">
            🎁 У вас скидка 50% по приглашению!
            <div v-if="me.discount_expires_at" class="discount-exp">
              Действует до {{ formatDateFull(me.discount_expires_at) }}
            </div>
          </div>

          <div class="price-row">
            <template v-if="me?.has_discount">
              <span class="price-old">{{ regularPrice }} ₽</span>
              <span class="price-big">{{ discountPrice }} ₽</span>
            </template>
            <template v-else>
              <span class="price-big">{{ regularPrice }} ₽</span>
            </template>
            <span class="price-per">/мес</span>
          </div>
          <button class="btn-primary sub-btn" :disabled="actionLoading" @click="openPaywall">
            {{ actionLoading ? 'Загрузка...' : 'Оформить подписку' }}
          </button>
          <p class="disclaimer">Автоматическое продление каждые 30 дней. Можно отменить в любой момент.</p>
        </div>

        <!-- Active, will renew (monthly) -->
        <div v-else-if="subInfo.status === 'active' && !subInfo.cancel_at_period_end && subInfo.plan_type !== 'world_cup'" class="sub-card">
          <div class="sub-icon">✅</div>
          <h2 class="sub-title">Подписка активна</h2>
          <div v-if="subInfo.plan_type === 'monthly'" class="plan-badge plan-badge--monthly">Месячный тариф</div>
          <p class="sub-desc">
            Следующее списание: <strong>{{ formatDate(subInfo.current_period_end!) }}</strong>
            — {{ regularPrice }} ₽
          </p>
          <button class="btn-secondary sub-btn" :disabled="actionLoading" @click="handleCancel">
            {{ actionLoading ? 'Загрузка...' : 'Отменить автопродление' }}
          </button>
          <p v-if="actionError" class="error-msg">{{ actionError }}</p>
        </div>

        <!-- Active, world_cup plan -->
        <div v-else-if="subInfo.status === 'active' && subInfo.plan_type === 'world_cup'" class="sub-card">
          <div class="sub-icon">🏆</div>
          <h2 class="sub-title">Пакет Чемпионата мира</h2>
          <div class="plan-badge plan-badge--worldcup">Пакет ЧМ</div>
          <p class="sub-desc">
            Доступ действует до <strong>19 июля 2026</strong> — до конца Чемпионата мира.
          </p>
        </div>

        <!-- Active, cancel at period end -->
        <div v-else-if="subInfo.status === 'active' && subInfo.cancel_at_period_end" class="sub-card">
          <div class="sub-icon">⏳</div>
          <h2 class="sub-title">Подписка активна</h2>
          <p class="sub-desc">
            Автопродление отключено. Доступ сохранится до <strong>{{ formatDate(subInfo.current_period_end!) }}</strong>
          </p>
          <button class="btn-primary sub-btn" :disabled="actionLoading" @click="handleResume">
            {{ actionLoading ? 'Загрузка...' : 'Возобновить подписку' }}
          </button>
          <p v-if="actionError" class="error-msg">{{ actionError }}</p>
        </div>

        <!-- Past due -->
        <div v-else-if="subInfo.status === 'past_due'" class="sub-card">
          <div class="sub-icon">⚠️</div>
          <h2 class="sub-title">Ошибка списания</h2>
          <p class="sub-desc">Не удалось списать платёж. Обновите платёжный метод для продолжения подписки.</p>
          <button class="btn-primary sub-btn" :disabled="actionLoading" @click="openPaywall">
            {{ actionLoading ? 'Загрузка...' : 'Обновить карту' }}
          </button>
          <p v-if="actionError" class="error-msg">{{ actionError }}</p>
        </div>

        <!-- Expired / canceled -->
        <div v-else class="sub-card">
          <div class="sub-icon">🔓</div>
          <h2 class="sub-title">Подписка завершена</h2>
          <p class="sub-desc">Оформите подписку снова, чтобы восстановить безлимитный доступ.</p>
          <div class="price-row">
            <span class="price-big">{{ regularPrice }} ₽</span>
            <span class="price-per">/мес</span>
          </div>
          <button class="btn-primary sub-btn" :disabled="actionLoading" @click="openPaywall">
            Оформить подписку
          </button>
          <p class="disclaimer">Автоматическое продление каждые 30 дней. Можно отменить в любой момент.</p>
        </div>

        <!-- Referral block -->
        <ReferralCard embedded />
      </template>
    </div>

    <PaywallSheet :open="paywallOpen" @close="paywallOpen = false; load()" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import {
  getBillingMe,
  getBillingConfig,
  cancelSubscription,
  resumeSubscription,
  type BillingMeResponse,
} from '../api'
import PaywallSheet from '../components/PaywallSheet.vue'
import ReferralCard from '../components/ReferralCard.vue'
import { formatMoscowDateTime } from '../lib/moscowTime'

const loading = ref(true)
const actionLoading = ref(false)
const actionError = ref('')
const subInfo = ref<BillingMeResponse | null>(null)
const me = ref<BillingMeResponse | null>(null)
const regularPrice = ref(0)
const discountPrice = ref(0)
const paywallOpen = ref(false)

const quotaPercent = computed(() => {
  const q = me.value?.quota
  if (!q || q.is_unlimited) return 0
  return Math.round((q.used / q.weekly_limit) * 100)
})

async function load() {
  loading.value = true
  try {
    const [meResp, cfg] = await Promise.all([
      getBillingMe(),
      getBillingConfig(),
    ])
    me.value = meResp
    regularPrice.value = Math.round(cfg.price_rub)
    discountPrice.value = Math.round(cfg.discount_price_rub)

    const hasActive = meResp.is_subscribed || (meResp.status && meResp.status !== 'expired' && meResp.status !== 'canceled')
    subInfo.value = hasActive ? meResp : null
  } catch {
    subInfo.value = null
  } finally {
    loading.value = false
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function formatDateFull(iso: string): string {
  return formatMoscowDateTime(iso)
}

function openPaywall() {
  paywallOpen.value = true
}

async function handleCancel() {
  actionLoading.value = true
  actionError.value = ''
  try {
    await cancelSubscription()
    await load()
  } catch {
    actionError.value = 'Не удалось отменить. Попробуйте позже.'
  } finally {
    actionLoading.value = false
  }
}

async function handleResume() {
  actionLoading.value = true
  actionError.value = ''
  try {
    await resumeSubscription()
    await load()
  } catch {
    actionError.value = 'Не удалось возобновить. Попробуйте позже.'
  } finally {
    actionLoading.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('billing-updated', load)
})

onBeforeUnmount(() => {
  window.removeEventListener('billing-updated', load)
})
</script>

<style scoped>
.sub-page {
  padding-bottom: calc(var(--bottom-nav-current-height) + 12px + env(safe-area-inset-bottom));
}

.sub-content {
  padding: 16px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.quota-card {
  background: var(--card, #fff);
  border-radius: var(--radius, 12px);
  padding: 16px 18px;
}

.quota-card-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.quota-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.quota-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
}

.quota-bar {
  height: 6px;
  background: #e6e9ed;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}

.quota-bar-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 3px;
  transition: width 0.4s;
}

.quota-reset {
  font-size: 12px;
  color: var(--text-secondary);
}

.sub-card {
  background: var(--card, #fff);
  border-radius: var(--radius, 12px);
  padding: 24px 20px;
  text-align: center;
}

.sub-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.sub-title {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 8px;
}

.sub-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 16px;
}

.plan-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 12px;
}

.plan-badge--monthly {
  background: #eef2ff;
  color: var(--primary, #2563eb);
}

.plan-badge--worldcup {
  background: #fff8e1;
  color: #e65100;
}

.discount-banner {
  background: #d4edda;
  border: 1px solid #28a745;
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #155724;
  font-weight: 500;
}

.discount-exp {
  font-size: 11px;
  margin-top: 4px;
  opacity: 0.8;
}

.price-row {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 6px;
  margin-bottom: 16px;
}

.price-big {
  font-size: 32px;
  font-weight: 700;
  color: var(--primary);
}

.price-old {
  font-size: 18px;
  color: var(--text-secondary);
  text-decoration: line-through;
}

.price-per {
  font-size: 14px;
  color: var(--text-secondary);
}

.btn-primary, .btn-secondary {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
  margin-bottom: 10px;
}

.btn-primary {
  background: var(--primary, #2563eb);
  color: #fff;
}

.btn-secondary {
  background: #f4f6f9;
  color: #333;
}

.btn-primary:disabled, .btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.disclaimer {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.error-msg {
  color: #ef4444;
  font-size: 13px;
  margin: 4px 0 0;
}
</style>
