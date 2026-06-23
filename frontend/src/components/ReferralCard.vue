<template>
  <section class="referral-card" :class="{ 'referral-card--embedded': embedded }">
    <h2 class="referral-title">Пригласи друга</h2>
    <p class="referral-desc">
      Друг получает скидку 50% на первую подписку в течение 24 часов после регистрации.
      Ты получаешь месяц подписки бесплатно после их оплаты.
    </p>

    <div v-if="loading && !loaded" class="referral-skeleton" aria-hidden="true">
      <div class="skeleton-line skeleton-line--short" />
      <div class="skeleton-line skeleton-line--long" />
    </div>

    <template v-else>
      <div v-if="referralLink" class="referral-link-block">
        <div class="referral-link-label">Твоя ссылка</div>
        <div class="referral-link-row">
          <span class="referral-link-text">{{ referralLink }}</span>
          <button type="button" class="copy-btn" @click="copyLink">
            {{ copied ? 'Скопировано!' : 'Копировать' }}
          </button>
        </div>
      </div>
      <p v-else-if="loaded && referralCode" class="referral-empty">
        Ссылка временно недоступна. Обратитесь к администратору — нужно указать имя бота в настройках.
      </p>
      <p v-else-if="loaded" class="referral-empty">
        Не удалось загрузить ссылку. Закройте и откройте приложение снова.
      </p>

      <div v-if="referralStats" class="referral-stats">
        <span>Приглашено: <strong>{{ referralStats.referred_count }}</strong></span>
        <span>Оплатили: <strong>{{ referralStats.converted_count }}</strong></span>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useBillingProfile } from '../composables/useBillingProfile'

defineProps<{ embedded?: boolean }>()

const { state, loaded, loading, referralLink, ensureLoaded, refresh } = useBillingProfile()
const referralStats = computed(() => state.referralStats)
const referralCode = computed(() => state.me?.referral_code ?? null)
const copied = ref(false)

async function copyLink() {
  if (!referralLink.value) return
  try {
    await navigator.clipboard.writeText(referralLink.value)
    copied.value = true
    window.setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    // clipboard unavailable
  }
}

onMounted(() => {
  ensureLoaded()
  window.addEventListener('billing-updated', refresh)
})

onBeforeUnmount(() => {
  window.removeEventListener('billing-updated', refresh)
})
</script>

<style scoped>
.referral-card {
  margin: 16px 8px 0;
  background: var(--card, #fff);
  border-radius: 16px;
  padding: 20px 16px;
}

.referral-card--embedded {
  margin: 0;
  border-radius: var(--radius, 12px);
}

.referral-title {
  margin: 0 0 8px;
  color: #222;
  font-size: 16px;
  font-weight: 600;
  line-height: 22px;
}

.referral-desc {
  margin: 0 0 14px;
  color: var(--text-secondary, #6b7280);
  font-size: 14px;
  line-height: 1.45;
}

.referral-skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(90deg, #eceff4 25%, #f8f9fb 50%, #eceff4 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}

.skeleton-line--short {
  width: 40%;
}

.skeleton-line--long {
  width: 100%;
  height: 44px;
  border-radius: 10px;
}

.referral-empty {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}

.referral-link-block {
  margin-bottom: 12px;
}

.referral-link-label {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
}

.referral-link-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f4f6f9;
  border-radius: 10px;
}

.referral-link-text {
  flex: 1;
  font-size: 12px;
  line-height: 1.35;
  word-break: break-all;
  color: var(--primary, #3346d8);
}

.copy-btn {
  flex-shrink: 0;
  padding: 7px 12px;
  border: none;
  border-radius: 8px;
  background: var(--primary, #3346d8);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.referral-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}

.referral-stats strong {
  color: #222;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
