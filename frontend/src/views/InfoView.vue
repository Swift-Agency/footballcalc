<template>
  <div class="profile-page">
    <div class="profile-cover">
      <div class="profile-head">
        <div
          class="profile-avatar-wrap"
          :class="{ 'profile-avatar-wrap--subscribed': isSubscribed }"
        >
          <img
            v-if="photoUrl"
            :src="photoUrl"
            alt=""
            class="profile-avatar"
          />
          <div v-else class="profile-avatar profile-avatar--placeholder">
            {{ initials }}
          </div>
        </div>

        <div class="profile-text">
          <div class="profile-name">{{ displayName }}</div>
          <div v-if="username" class="profile-username">@{{ username }}</div>
        </div>
      </div>
    </div>

    <section class="access-card" :class="{ 'access-card--active': isSubscribed }">
      <div class="access-card-inner">
        <template v-if="isSubscribed">
          <h2 class="access-title">
            <template v-if="state.me?.plan_type === 'world_cup'">🏆 Пакет ЧМ активен</template>
            <template v-else>Подписка активна</template>
          </h2>
          <p v-if="periodEnd" class="access-desc">
            <template v-if="state.me?.plan_type === 'world_cup'">
              Безлимитный доступ к xG и калькулятору до 19 июля 2026
            </template>
            <template v-else>
              Безлимитный доступ к xG и калькулятору до {{ periodEnd }}
            </template>
          </p>
          <button class="access-cta access-cta--secondary" @click="router.push('/info/subscription')">
            Управление подпиской
          </button>
        </template>
        <template v-else>
          <h2 class="access-title">xG и Калькулятор</h2>
          <p class="access-desc">
            Все лиги открыты бесплатно. xG-таблицы и калькулятор коэффициентов —
            <span v-if="loading && !loaded" class="inline-skeleton">···</span>
            <template v-else>{{ remaining }} из {{ weeklyLimit }}</template>
            бесплатных запросов осталось на этой неделе.
          </p>
          <p v-if="hasDiscount" class="access-discount">
            🎁 Скидка 50% по приглашению — {{ discountPrice }} ₽ вместо {{ regularPrice }} ₽
            <span v-if="discountExpiresAt" class="access-discount-exp">
              до {{ formatMoscowDateTime(discountExpiresAt) }}
            </span>
          </p>
          <button class="access-cta" @click="openPaywall">
            <span v-if="hasDiscount">Оформить за {{ discountPrice }} ₽</span>
            <span v-else>Получить безлимитный доступ</span>
          </button>
        </template>
      </div>
    </section>

    <ReferralCard />

    <section class="info-block">
      <h2 class="info-block-title">Информация</h2>

      <button
        v-for="(item, idx) in items"
        :key="item.slug"
        class="info-row"
        @click="openItem(item.slug)"
      >
        <span class="row-icon">
          <svg
            v-if="idx === 0"
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 18 18"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M16.8007 8.45402C16.8007 12.6806 13.2181 16.1072 8.80024 16.1072C8.27914 16.1078 7.76312 16.0603 7.25215 15.9648C6.88493 15.8952 6.70173 15.8608 6.57372 15.8808C6.44571 15.9 6.2633 15.9968 5.90008 16.1896C4.8651 16.7408 3.6742 16.9261 2.5207 16.7153C2.96132 16.1706 3.26011 15.5252 3.39035 14.8368C3.47035 14.4127 3.27194 14.0007 2.97432 13.6991C1.62705 12.3294 0.799805 10.4845 0.799805 8.45402C0.799805 4.22739 4.3824 0.800003 8.80024 0.800003C13.2181 0.800003 16.8007 4.22739 16.8007 8.45402Z"
              stroke="#222222"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              d="M7.2002 7.07715C7.2002 6.2611 7.91623 5.60027 8.80028 5.60027C9.68433 5.60027 10.4004 6.2619 10.4004 7.07715C10.4004 7.37156 10.3076 7.64518 10.1468 7.87559C9.66833 8.56043 8.80028 9.21566 8.80028 10.0317V10.4005M8.80028 12.4006H8.80748"
              stroke="#222222"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <svg
            v-else
            xmlns="http://www.w3.org/2000/svg"
            width="13"
            height="16"
            viewBox="0 0 15 18"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M9.50049 1.10028V2.30028C9.50049 3.43148 9.50049 3.99708 9.85249 4.34828C10.2029 4.70028 10.7685 4.70028 11.9005 4.70028H13.1005"
              stroke="#222222"
              stroke-width="1.4"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              d="M3.9002 7.90032H10.3002M3.9002 10.3003H10.3002M3.9002 12.7003H7.2362M0.700195 11.9003V5.50032C0.700195 3.23792 0.700195 2.10592 1.4034 1.40352C2.1058 0.700317 3.2378 0.700317 5.5002 0.700317H8.8378C9.1642 0.700317 9.3282 0.700317 9.4754 0.761117C9.6218 0.821917 9.7378 0.937117 9.969 1.16912L13.0314 4.23152C13.2634 4.46352 13.3786 4.57872 13.4394 4.72592C13.5002 4.87232 13.5002 5.03632 13.5002 5.36272V11.9003C13.5002 14.1627 13.5002 15.2947 12.797 15.9971C12.0946 16.7003 10.9626 16.7003 8.7002 16.7003H5.5002C3.2378 16.7003 2.1058 16.7003 1.4034 15.9971C0.700195 15.2947 0.700195 14.1627 0.700195 11.9003Z"
              stroke="#222222"
              stroke-width="1.4"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </span>
        <span class="row-label">{{ item.label }}</span>
      </button>
    </section>

    <PaywallSheet :open="paywallOpen" @close="paywallOpen = false" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { getTelegram } from '../telegram'
import { useBillingProfile } from '../composables/useBillingProfile'
import { formatMoscowDateTime } from '../lib/moscowTime'
import PaywallSheet from '../components/PaywallSheet.vue'
import ReferralCard from '../components/ReferralCard.vue'

const router = useRouter()
const paywallOpen = ref(false)
const periodEnd = ref('')

const { state, loaded, loading, isSubscribed, remaining, weeklyLimit, hasDiscount, discountExpiresAt, regularPrice, discountPrice, ensureLoaded, refresh } =
  useBillingProfile()

const tgUser = computed(() => getTelegram()?.initDataUnsafe?.user)

const displayName = computed(() => {
  const u = tgUser.value
  if (!u) return 'Гость'
  const parts = [u.first_name, u.last_name].filter(Boolean)
  return parts.join(' ') || u.username || 'Пользователь'
})

const username = computed(() => tgUser.value?.username || '')
const photoUrl = computed(() => tgUser.value?.photo_url || '')

const initials = computed(() => {
  const name = displayName.value.trim()
  return name ? name.charAt(0).toUpperCase() : '?'
})

const items = [
  { slug: 'faq', label: 'Вопросы и ответы' },
  { slug: 'glossary', label: 'Глоссарий терминов' },
  { slug: 'other', label: 'Другое' },
]

function openItem(slug: string) {
  router.push(`/info/${slug}`)
}

function openPaywall() {
  paywallOpen.value = true
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

function syncPeriodEnd() {
  if (state.me?.is_subscribed && state.me.current_period_end) {
    periodEnd.value = formatDate(state.me.current_period_end)
  } else {
    periodEnd.value = ''
  }
}

async function reloadFromEvent() {
  await refresh()
  syncPeriodEnd()
}

onMounted(() => {
  ensureLoaded().then(syncPeriodEnd)
  window.addEventListener('billing-updated', reloadFromEvent)
})

onBeforeUnmount(() => {
  window.removeEventListener('billing-updated', reloadFromEvent)
})
</script>

<style scoped>
.profile-page {
  padding-bottom: calc(var(--bottom-nav-current-height) + env(safe-area-inset-bottom));
}

.profile-cover {
  box-sizing: border-box;
  padding: calc(56px + var(--app-safe-top) + var(--header-title-offset)) 16px 24px;
  background:
    linear-gradient(165deg, #3346d8 0%, #2c3ec4 45%, #1e2f9e 100%);
  border-radius: 0 0 24px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.profile-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  width: 100%;
}

.profile-avatar-wrap {
  width: 112px;
  height: 112px;
  border-radius: 50%;
  padding: 4px;
  background: transparent;
}

.profile-avatar-wrap--subscribed {
  background: linear-gradient(180deg, #ffd54f 0%, #ffb300 100%);
  box-shadow: 0 0 0 4px rgba(255, 179, 0, 0.25);
}

.profile-avatar {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  background: #eceff4;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 600;
  color: #3346d8;
  border: 3px solid #fff;
}

.profile-avatar--placeholder {
  border: 3px solid #fff;
}

.profile-text {
  margin-top: 12px;
  width: 100%;
  max-width: 280px;
}

.profile-name {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  line-height: 22px;
}

.profile-username {
  margin-top: 2px;
  color: rgba(255, 255, 255, 0.75);
  font-size: 16px;
  font-weight: 500;
  line-height: 22px;
}

.access-card {
  margin: 16px 8px 0;
  border-radius: 16px;
  overflow: hidden;
  background: linear-gradient(145deg, #1a2568 0%, #121b52 100%);
  box-shadow: 0 8px 24px rgba(18, 27, 82, 0.24);
}

.access-card--active {
  background: linear-gradient(145deg, #1a2568 0%, #121b52 100%);
}

.access-card-inner {
  padding: 24px 16px 20px;
}

.access-title {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  line-height: 22px;
}

.access-desc {
  margin-top: 8px;
  color: rgba(255, 255, 255, 0.75);
  font-size: 14px;
  font-weight: 500;
  line-height: 20px;
}

.access-discount {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 213, 79, 0.14);
  border: 1px solid rgba(255, 213, 79, 0.35);
  color: #ffe082;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}

.access-discount-exp {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 224, 130, 0.85);
}

.inline-skeleton {
  display: inline-block;
  min-width: 48px;
  color: rgba(255, 255, 255, 0.45);
}

.access-cta {
  margin-top: 20px;
  width: 100%;
  min-height: 64px;
  border: none;
  border-radius: 16px;
  background: linear-gradient(90deg, #ffd54f 0%, rgba(255, 213, 79, 0.35) 100%);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  line-height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}

.access-cta:disabled {
  opacity: 0.7;
}

.access-cta--secondary {
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.info-block {
  margin: 16px 8px 0;
  background: var(--card);
  border-radius: 16px;
  overflow: hidden;
  padding-bottom: 8px;
}

.info-block-title {
  padding: 24px 16px 8px;
  color: #222;
  font-size: 16px;
  font-weight: 600;
  line-height: 22px;
}

.info-row {
  width: calc(100% - 32px);
  margin: 0 16px;
  padding: 12px 0;
  border: none;
  border-bottom: 1px solid #e6e9ed;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  cursor: pointer;
}

.info-row:last-child {
  border-bottom: none;
}

.row-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #eceff4;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.row-label {
  flex: 1;
  color: #222;
  font-size: 16px;
  font-weight: 500;
  line-height: 21px;
}
</style>
