<template>
  <button
    type="button"
    class="wc-banner"
    aria-label="Чемпионат мира — 11 июня — 19 июля 2026 года"
    @click="$emit('click')"
  >
    <img
      :src="bannerSrc"
      :srcset="`${bannerSrc} 1x, ${banner2xSrc} 2x`"
      alt=""
      class="wc-banner-img"
      draggable="false"
      width="377"
      height="211"
    />
    <div class="wc-banner-text">
      <div class="wc-banner-title">Чемпионат мира</div>
      <div class="wc-banner-sub">11 июня — 19 июля 2026 года</div>
    </div>
    <div v-if="locked" class="wc-lock">
      <LockIcon :size="16" />
    </div>
  </button>
</template>

<script setup lang="ts">
import LockIcon from './LockIcon.vue'

defineProps<{
  locked?: boolean
}>()

defineEmits<{ (e: 'click'): void }>()

const base = import.meta.env.BASE_URL
const root = base.endsWith('/') ? base : `${base}/`
const bannerSrc = `${root}banners/world-cup-banner-bg.png`
const banner2xSrc = `${root}banners/world-cup-banner-bg@2x.png`
</script>

<style scoped>
.wc-banner {
  position: relative;
  display: block;
  width: calc(100% - 16px);
  margin: 16px 8px;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  transition: transform 0.15s;
  z-index: 1;
}

.wc-banner:active {
  transform: scale(0.98);
}

.wc-banner-img {
  display: block;
  width: 100%;
  height: auto;
  /* Figma frame: blue card starts at y=41, empty tail at bottom ≈42px */
  margin-top: -41px;
  margin-bottom: -42px;
  border-radius: 16px;
  user-select: none;
  pointer-events: none;
}

.wc-banner-text {
  position: absolute;
  left: 4.5%;
  top: 50%;
  transform: translateY(-50%);
  text-align: left;
  pointer-events: none;
}

.wc-banner-title {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  line-height: 1.15;
  white-space: nowrap;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
}

.wc-banner-sub {
  font-size: 13px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.78);
  line-height: 1.15;
  margin-top: 4px;
  white-space: nowrap;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.wc-lock {
  position: absolute;
  right: 16px;
  bottom: 16px;
  z-index: 2;
  color: rgba(255, 255, 255, 0.85);
}
</style>
