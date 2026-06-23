<template>
  <Teleport to="body">
    <div v-if="visible" class="payment-overlay">
      <div class="payment-card">
        <div v-if="phase === 'polling'" class="payment-spinner" aria-hidden="true" />
        <div v-else-if="phase === 'success'" class="payment-icon payment-icon--ok">✓</div>
        <div v-else class="payment-icon payment-icon--warn">!</div>
        <p class="payment-message">{{ message }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { paymentPollMessage, paymentPollPhase, type PaymentPollPhase } from '../composables/usePendingPayment'

const phase = computed(() => paymentPollPhase.value as PaymentPollPhase)
const message = computed(() => paymentPollMessage.value)
const visible = computed(() => phase.value !== 'idle' && message.value.length > 0)
</script>

<style scoped>
.payment-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.payment-card {
  width: 100%;
  max-width: 320px;
  background: #fff;
  border-radius: 16px;
  padding: 28px 20px;
  text-align: center;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
}

.payment-spinner {
  width: 36px;
  height: 36px;
  margin: 0 auto 16px;
  border: 3px solid #e6e9ed;
  border-top-color: var(--primary, #3346d8);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.payment-icon {
  width: 44px;
  height: 44px;
  margin: 0 auto 14px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
}

.payment-icon--ok {
  background: #d1fae5;
  color: #059669;
}

.payment-icon--warn {
  background: #fef3c7;
  color: #d97706;
}

.payment-message {
  margin: 0;
  font-size: 15px;
  line-height: 1.45;
  color: var(--text, #1f2937);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
