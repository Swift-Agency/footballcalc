<template>
  <div class="gradient-header">
    <img
      v-if="logoUrl && !imgFailed"
      :src="logoUrl"
      :alt="name"
      class="league-logo"
      @error="onImgError"
    />
    <div v-else class="league-logo-placeholder">{{ initials }}</div>
    <div class="league-meta">
      <p class="league-title">{{ name }}</p>
      <p v-if="subtitle" class="league-subtitle">{{ subtitle }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  name: string
  logoUrl?: string | null
  subtitle?: string | null
}>()

const imgFailed = ref(false)

watch(
  () => props.logoUrl,
  () => {
    imgFailed.value = false
  },
)

const initials = computed(() =>
  props.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 3)
    .toUpperCase(),
)

function onImgError() {
  console.warn('[LeagueHeader] logo failed to load:', props.logoUrl)
  imgFailed.value = true
}
</script>

<style scoped>
.league-logo {
  width: 139.641px;
  height: 58.818px;
  aspect-ratio: 139.641 / 58.818;
  object-fit: contain;
  display: block;
  /* drop-shadow so white logos are visible on the blue gradient */
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.18));
}

.league-logo-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 700;
  color: white;
  backdrop-filter: blur(4px);
}

.league-meta {
  margin-top: 10px;
  text-align: center;
  color: #fff;
}

.league-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.2;
}

.league-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.2;
  opacity: 0.9;
}
</style>
