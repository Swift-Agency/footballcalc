<template>
  <div id="app-root" :class="{ 'nav-back-mode': !isNavRoot }">
    <div v-if="showApiConfigBanner" class="api-config-banner">
      <p><strong>API not configured</strong></p>
      <p>Set <code>VITE_API_URL</code> in Vercel to your backend URL (e.g. <code>https://your-api.railway.app/api</code>), then redeploy.</p>
    </div>
    <router-view v-slot="{ Component }">
      <component v-if="Component" :is="Component" :key="route.fullPath" />
    </router-view>
    <div v-if="legalBlocked" class="legal-block-overlay">
      <div class="legal-block-card">
        <h3>Требуется подтверждение условий</h3>
        <p>Откройте бота, нажмите /start и далее кнопку «Принимаю условия».</p>
      </div>
    </div>
    <BottomNav />
    <PaymentStatusOverlay />
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getTelegram } from './telegram'
import { isApiConfigured } from './api'
import { postAppEvent } from './analytics'
import { isRootPath, navigateBack } from './navigation'
import { ensureBillingProfileLoaded, useBillingProfile } from './composables/useBillingProfile'
import { resumePendingPayment } from './composables/usePendingPayment'
import BottomNav from './components/BottomNav.vue'
import PaymentStatusOverlay from './components/PaymentStatusOverlay.vue'

const showApiConfigBanner = computed(() => {
  if (typeof window === 'undefined') return false
  if (/localhost|127\.0\.0\.1/.test(window.location.host)) return false
  return !isApiConfigured()
})

const router = useRouter()
const route = useRoute()
const { legalBlocked } = useBillingProfile()

const isNavRoot = computed(() => isRootPath(route.path))

function handleBack() {
  console.debug('[App] Telegram BackButton → navigateBack from', route.path)
  navigateBack(router, route)
}

watch(
  () => route.path,
  (path) => {
    console.debug('[App] route changed →', path)
    const tg = getTelegram()
    if (!tg) return

    if (isRootPath(path)) {
      tg.BackButton.hide()
    } else {
      tg.BackButton.show()
    }
  },
  { immediate: true },
)

watch(
  () => route.path,
  (path) => {
    const tg = getTelegram()
    const uid = tg?.initDataUnsafe?.user?.id
    postAppEvent('page_view', { path }, typeof uid === 'number' ? uid : undefined)
  },
  { immediate: true },
)

onMounted(async () => {
  const tg = getTelegram()
  if (tg) {
    tg.BackButton.onClick(handleBack)
    tg.onEvent('viewport_changed', tryResumePayment)
  }

  document.addEventListener('visibilitychange', onVisibilityChange)
  await ensureBillingProfileLoaded()
  tryResumePayment()
})

onUnmounted(() => {
  const tg = getTelegram()
  if (tg) {
    tg.BackButton.offClick(handleBack)
  }
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

function onVisibilityChange() {
  if (document.visibilityState === 'visible') {
    tryResumePayment()
  }
}

function tryResumePayment() {
  resumePendingPayment().catch((err) => {
    console.error('[App] resumePendingPayment failed:', err)
  })
}
</script>

<style scoped>
.api-config-banner {
  background: #fef3c7;
  color: #92400e;
  padding: 12px 16px;
  font-size: 13px;
  border-bottom: 1px solid #f59e0b;
}
.api-config-banner code {
  background: rgba(0,0,0,.08);
  padding: 2px 6px;
  border-radius: 4px;
}

.legal-block-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(15, 23, 42, 0.72);
}

.legal-block-card {
  width: 100%;
  max-width: 440px;
  border-radius: 16px;
  background: #ffffff;
  color: #111827;
  padding: 20px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.25);
}

.legal-block-card h3 {
  margin: 0 0 8px 0;
}

.legal-block-card p {
  margin: 0;
  line-height: 1.4;
}
</style>
