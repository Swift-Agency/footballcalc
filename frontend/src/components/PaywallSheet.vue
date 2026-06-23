<template>
  <Teleport to="body">
    <transition name="sheet">
      <div v-if="open" class="sheet-overlay" @click.self="$emit('close')">
        <div class="sheet-container">
          <div class="sheet-handle"></div>
          <div class="sheet-content">
            <div class="paywall-icon">⚡</div>
            <h2 class="paywall-title">Премиум-доступ</h2>
            <p class="paywall-sub">xG-таблицы и калькулятор коэффициентов</p>

            <!-- Quota status -->
            <div v-if="quota && !quota.is_unlimited" class="quota-badge">
              <span class="quota-used">
                Использовано {{ quota.used }} из {{ quota.weekly_limit }} бесплатных запросов на этой неделе
              </span>
              <span v-if="quota.resets_at" class="quota-reset">
                Обновление: {{ formatResetDate(quota.resets_at) }}
              </span>
            </div>

            <ul class="perks-list">
              <li>📊 xG-таблицы — ожидаемые голы по каждой лиге</li>
              <li>🧮 Калькулятор коэффициентов (модель Пуассона)</li>
              <li>✅ Все лиги и базовые разделы уже бесплатны</li>
            </ul>

            <!-- Plan selector -->
            <div class="plan-tabs">
              <button
                :class="['plan-tab', { 'plan-tab--active': selectedPlan === 'monthly' }]"
                @click="selectedPlan = 'monthly'"
              >
                <span class="plan-tab-label">Месячная</span>
                <span class="plan-tab-price">{{ effectivePrice }} ₽/мес</span>
              </button>
              <button
                :class="['plan-tab', { 'plan-tab--active': selectedPlan === 'world_cup' }]"
                @click="selectedPlan = 'world_cup'"
              >
                <span class="plan-tab-label">🏆 Пакет ЧМ</span>
                <span class="plan-tab-price">{{ effectivePrice }} ₽</span>
                <span class="plan-tab-sub">до 19 июля</span>
              </button>
            </div>

            <!-- Discount badge -->
            <div v-if="hasDiscount" class="discount-badge">
              🎁 Скидка 50% по приглашению — {{ discountPrice }} ₽ вместо {{ regularPrice }} ₽
              <div v-if="discountExpiresAt" class="discount-expires">
                Действует до {{ formatDiscountExpiry(discountExpiresAt) }}
              </div>
            </div>

            <div class="price-block">
              <template v-if="hasDiscount">
                <span class="price-old">{{ regularPrice }} ₽</span>
                <span class="price-amount">{{ discountPrice }} ₽</span>
              </template>
              <template v-else>
                <span class="price-amount">{{ regularPrice }} ₽</span>
              </template>
              <span class="price-period">{{ selectedPlan === 'world_cup' ? ' / весь ЧМ' : '/месяц' }}</span>
            </div>

            <button
              class="btn-primary paywall-btn"
              :disabled="loading"
              @click="startCheckout"
            >
              {{ loading ? 'Загрузка...' : 'Оформить подписку' }}
            </button>

            <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

            <p class="disclaimer">
              <template v-if="selectedPlan === 'monthly'">
                Автоматическое продление каждые 30 дней. Можно отменить в любой момент.
              </template>
              <template v-else>
                Единовременный платёж. Доступ действует до 19 июля 2026 года.
              </template>
            </p>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { createCheckout, type UsageQuota } from '../api'
import { checkoutReturnUrl, savePendingPayment } from '../composables/usePendingPayment'
import { useBillingProfile } from '../composables/useBillingProfile'
import { formatMoscowDateTime } from '../lib/moscowTime'

const props = defineProps<{
  open: boolean
  quotaOverride?: UsageQuota | null
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const {
  state,
  regularPrice,
  discountPrice,
  hasDiscount,
  discountExpiresAt,
  ensureLoaded,
} = useBillingProfile()
const quota = ref<UsageQuota | null>(null)
const selectedPlan = ref<'monthly' | 'world_cup'>('monthly')
const loading = ref(false)
const errorMsg = ref('')

const effectivePrice = computed(() => hasDiscount.value ? discountPrice.value : regularPrice.value)

async function loadConfig() {
  try {
    await ensureLoaded()
    if (props.quotaOverride) {
      quota.value = props.quotaOverride
    } else {
      quota.value = state.me?.quota ?? null
    }
  } catch {
    // fallback stays
  }
}

watch(() => props.open, (val) => {
  if (val) loadConfig()
})

onMounted(() => {
  if (props.open) loadConfig()
})

function formatResetDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
  } catch {
    return iso
  }
}

function formatDiscountExpiry(iso: string): string {
  return formatMoscowDateTime(iso)
}

async function startCheckout() {
  loading.value = true
  errorMsg.value = ''
  try {
    const returnUrl = checkoutReturnUrl()
    const resp = await createCheckout({ return_url: returnUrl, plan_type: selectedPlan.value })
    savePendingPayment(resp.payment_id)
    emit('close')
    window.location.href = resp.confirmation_url
  } catch (e: any) {
    const detail = e?.detail?.detail ?? e?.detail
    if (detail === 'already_subscribed') {
      errorMsg.value = 'У вас уже есть активная подписка'
    } else {
      errorMsg.value = 'Ошибка при создании платежа. Попробуйте ещё раз.'
    }
    loading.value = false
  }
}
</script>

<style scoped>
.sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: flex-end;
}

.sheet-container {
  background: var(--bg, #fff);
  border-radius: 20px 20px 0 0;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  padding-bottom: env(safe-area-inset-bottom, 16px);
}

.sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--border, #e6e9ed);
  border-radius: 2px;
  margin: 12px auto 0;
}

.sheet-content {
  padding: 16px 20px 24px;
  text-align: center;
}

.paywall-icon {
  font-size: 44px;
  margin-bottom: 10px;
}

.paywall-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 6px;
}

.paywall-sub {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 16px;
}

.quota-badge {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 16px;
  font-size: 13px;
}

.quota-used {
  display: block;
  font-weight: 600;
  color: #856404;
}

.quota-reset {
  display: block;
  color: #856404;
  margin-top: 4px;
  font-size: 12px;
}

.perks-list {
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.perks-list li {
  font-size: 14px;
  line-height: 1.4;
}

.plan-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.plan-tab {
  flex: 1;
  background: var(--card, #f4f6f9);
  border: 2px solid transparent;
  border-radius: 12px;
  padding: 10px 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: border-color 0.15s;
}

.plan-tab--active {
  border-color: var(--primary, #2563eb);
  background: #eef2ff;
}

.plan-tab-label {
  font-size: 13px;
  font-weight: 600;
}

.plan-tab-price {
  font-size: 15px;
  font-weight: 700;
  color: var(--primary, #2563eb);
}

.plan-tab-sub {
  font-size: 11px;
  color: var(--text-secondary);
}

.discount-badge {
  background: #d4edda;
  border: 1px solid #28a745;
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #155724;
  font-weight: 500;
}

.discount-expires {
  font-size: 11px;
  margin-top: 4px;
  color: #155724;
  opacity: 0.8;
}

.price-block {
  margin-bottom: 20px;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 6px;
}

.price-old {
  font-size: 18px;
  color: var(--text-secondary);
  text-decoration: line-through;
}

.price-amount {
  font-size: 32px;
  font-weight: 700;
  color: var(--primary);
}

.price-period {
  font-size: 14px;
  color: var(--text-secondary);
}

.btn-primary {
  width: 100%;
  padding: 16px;
  background: var(--primary, #2563eb);
  color: #fff;
  border: none;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.paywall-btn {
  margin-bottom: 12px;
}

.error-msg {
  color: #ef4444;
  font-size: 13px;
  margin: 0 0 8px;
}

.disclaimer {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.25s;
}

.sheet-enter-active .sheet-container,
.sheet-leave-active .sheet-container {
  transition: transform 0.25s ease;
}

.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}

.sheet-enter-from .sheet-container,
.sheet-leave-to .sheet-container {
  transform: translateY(100%);
}
</style>
