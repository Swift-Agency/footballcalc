<template>
  <button
    v-if="loaded"
    type="button"
    class="quota-banner"
    :class="{
      'quota-banner--unlimited': isUnlimited,
      'quota-banner--discount': hasDiscount && !isUnlimited,
    }"
    @click="goSubscription"
  >
    <div class="quota-banner-body">
      <span class="quota-banner-title">xG и калькулятор</span>
      <span v-if="isUnlimited" class="quota-banner-text">Безлимитный доступ</span>
      <span v-else class="quota-banner-text">
        {{ remaining }} из {{ weeklyLimit }} бесплатных запросов на неделе
      </span>
      <div v-if="!isUnlimited" class="quota-banner-bar" aria-hidden="true">
        <div class="quota-banner-bar-fill" :style="{ width: `${percentUsed}%` }" />
      </div>
      <div v-if="hasDiscount && !isUnlimited" class="quota-banner-discount">
        🎁 Скидка 50% — {{ discountPrice }} ₽ вместо {{ regularPrice }} ₽
        <span v-if="discountExpiresAt" class="quota-banner-discount-exp">
          до {{ formatMoscowDateTime(discountExpiresAt) }}
        </span>
      </div>
    </div>
    <span class="quota-banner-link">{{ hasDiscount && !isUnlimited ? 'Оплатить ›' : 'Подписка ›' }}</span>
  </button>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuotaStatus } from '../composables/useBillingProfile'
import { formatMoscowDateTime } from '../lib/moscowTime'

const router = useRouter()
const {
  loaded,
  isUnlimited,
  remaining,
  weeklyLimit,
  percentUsed,
  hasDiscount,
  discountExpiresAt,
  regularPrice,
  discountPrice,
  ensureLoaded,
} = useQuotaStatus()

onMounted(() => {
  ensureLoaded()
})

function goSubscription() {
  router.push('/info/subscription')
}
</script>

<style scoped>
.quota-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: calc(100% - 24px);
  margin: 0 12px 12px;
  padding: 12px 14px;
  border: none;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 10px rgba(51, 70, 216, 0.08);
  cursor: pointer;
  text-align: left;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.quota-banner:active {
  transform: scale(0.99);
}

.quota-banner--unlimited {
  background: linear-gradient(135deg, #eef1ff 0%, #f8f9ff 100%);
}

.quota-banner--discount {
  background: linear-gradient(135deg, #eefaf1 0%, #fff 100%);
  box-shadow: 0 2px 10px rgba(40, 167, 69, 0.12);
}

.quota-banner-body {
  flex: 1;
  min-width: 0;
}

.quota-banner-title {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 2px;
}

.quota-banner-text {
  display: block;
  font-size: 14px;
  line-height: 1.35;
  color: var(--text);
}

.quota-banner-bar {
  height: 4px;
  margin-top: 8px;
  background: #e6e9ed;
  border-radius: 2px;
  overflow: hidden;
}

.quota-banner-bar-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.quota-banner-discount {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #d4edda;
  border: 1px solid #28a745;
  font-size: 12px;
  line-height: 1.4;
  color: #155724;
  font-weight: 500;
}

.quota-banner-discount-exp {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  font-weight: 400;
  opacity: 0.85;
}

.quota-banner-link {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  white-space: nowrap;
}
</style>
