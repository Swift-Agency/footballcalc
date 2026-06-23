<template>
  <nav :class="['bottom-nav', { 'bottom-nav--back': !isRoot }]">
    <!-- Inner pages: single "Назад" button -->
    <template v-if="!isRoot">
      <button class="back-btn-nav" @click="handleBack">
        <span>Назад</span>
      </button>
    </template>

    <!-- Root leagues page: tab icons from menu icons -->
    <template v-else>
      <button
        v-for="tab in tabs"
        :key="tab.path"
        :class="['tab-btn', { active: isActive(tab.path) }]"
        @click="navigate(tab.path)"
      >
        <span class="nav-icon">
          <NavTabIcon :name="tab.icon" />
        </span>
      </button>
    </template>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { isRootPath, navigateBack, navigateRootTab } from '../navigation'
import NavTabIcon from './NavTabIcon.vue'

const router = useRouter()
const route = useRoute()

const isRoot = computed(() => isRootPath(route.path))

const tabs = [
  { path: '/schedule', icon: 'schedule' as const },
  { path: '/leagues', icon: 'leagues' as const },
  { path: '/calculator', icon: 'calculator' as const },
  { path: '/info', icon: 'profile' as const },
]

function isActive(path: string): boolean {
  if (path === '/leagues' && route.path === '/') return true
  return route.path.startsWith(path)
}

function navigate(path: string) {
  console.debug('[Nav] navigate to', path)
  navigateRootTab(router, route, path)
}

function handleBack() {
  console.debug('[Nav] back from', route.path)
  navigateBack(router, route)
}
</script>

<style scoped>
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  height: calc(var(--bottom-nav-current-height) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  display: flex;
  justify-content: space-around;
  align-items: center;
  background: var(--primary);
  border-radius: 20px 20px 0 0;
  z-index: 100;
  box-shadow: 0 -2px 16px rgba(51, 70, 216, 0.25);
}

.bottom-nav--back {
  border-radius: 24px 24px 0 0;
  background: #2C3EC4;
  box-shadow: 0 -8px 32px -4px rgba(44, 62, 196, 0.16);
}

.tab-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 100%;
  border: none;
  background: none;
  cursor: pointer;
  color: #959EE1;
  border-radius: 12px;
  transition: color 0.2s, background 0.2s;
  padding: 0;
}

.tab-btn.active {
  color: #FFFFFF;
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
}

.back-btn-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 44px;
  margin-top: 4px;
  border: none;
  background: none;
  cursor: pointer;
  color: #FFF;
  text-align: center;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 15px;
  font-style: normal;
  font-weight: 500;
  line-height: 20px;
  transition: opacity 0.15s;
}

.back-btn-nav:active {
  opacity: 0.7;
}
</style>
