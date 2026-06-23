<template>
  <div class="leagues-card">
    <div
      v-for="league in leagues"
      :key="league.id"
      class="league-row"
      @click="$emit('select', league)"
    >
      <img
        v-if="logoSrc(league)"
        :src="logoSrc(league)!"
        :alt="league.name"
        class="league-logo"
        @error="(e) => onLogoError(e, league)"
      />
      <div v-else class="league-logo-fallback">{{ fallbackIcon(league) }}</div>
      <span class="league-name">{{ league.name }}</span>
    </div>
    <div v-if="!loading && leagues.length === 0" class="empty">Лиги не найдены</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { League } from '../api'
import { getLeagueListLogo } from '../leagueLogos'

defineProps<{
  leagues: League[]
  loading?: boolean
}>()

defineEmits<{ (e: 'select', league: League): void }>()

const failedLogos = ref<Set<number>>(new Set())

const LEAGUE_ICONS: Record<number, string> = {
  1: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
  2: '⭐',
  3: '🟠',
  4: '🟢',
  5: '🇪🇸',
  6: '🇮🇹',
  7: '🇩🇪',
  8: '🇫🇷',
  9: '🇷🇺',
}

function fallbackIcon(league: League) {
  if (league.key === 'world_cup') return '🏆'
  return LEAGUE_ICONS[league.id] || '⚽'
}

function logoSrc(league: League): string | null {
  if (failedLogos.value.has(league.id)) return null
  return getLeagueListLogo(league)
}

function onLogoError(e: Event, league: League) {
  failedLogos.value = new Set([...failedLogos.value, league.id])
  ;(e.target as HTMLImageElement).style.display = 'none'
}
</script>

<style scoped>
.leagues-card {
  margin: 0 8px;
  background: var(--card);
  border-radius: 16px;
  overflow: hidden;
}

.league-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 56px;
  padding: 8px 16px;
  cursor: pointer;
  border-bottom: 1px solid #e6e9ed;
}

.league-row:last-child {
  border-bottom: none;
}

.league-row:active {
  background: #f8f9fb;
}

.league-logo,
.league-logo-fallback {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid #e6e9ed;
  background: #fff;
  object-fit: contain;
  padding: 4px;
}

.league-logo-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.league-name {
  flex: 1;
  color: #222;
  font-size: 16px;
  font-weight: 500;
  line-height: 22px;
}

.empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
