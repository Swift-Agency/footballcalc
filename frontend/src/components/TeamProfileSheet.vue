<template>
  <Teleport to="body">
    <Transition name="sheet-fade">
      <div
        v-if="open && team"
        class="team-sheet-overlay"
        aria-modal="true"
        role="dialog"
        :aria-labelledby="titleId"
        @click.self="emit('close')"
      >
        <div class="team-sheet-panel" @click.stop>
            <div class="team-sheet-grab" aria-hidden="true" />
            <header class="team-sheet-header">
              <div class="team-sheet-title-row">
                <img
                  v-if="team.logo_url"
                  :src="team.logo_url"
                  :alt="team.name"
                  class="team-sheet-logo"
                />
                <div v-else class="team-sheet-logo-fallback">{{ team.name.charAt(0) }}</div>
                <div class="team-sheet-titles">
                  <h2 :id="titleId" class="team-sheet-name">{{ team.name }}</h2>
                  <p v-if="leagueName" class="team-sheet-sub">{{ leagueName }}</p>
                </div>
              </div>
              <button type="button" class="team-sheet-close" aria-label="Закрыть" @click="emit('close')">
                ×
              </button>
            </header>

            <section class="team-sheet-section">
              <h3 class="team-sheet-h3">Расписание</h3>
              <p v-if="loadingMatches" class="team-sheet-muted">Загрузка…</p>
              <p v-else-if="matchesError" class="team-sheet-error">{{ matchesError }}</p>
              <ul v-else-if="upcomingMatches.length" class="team-sheet-matches">
                <li
                  v-for="m in upcomingMatches"
                  :key="m.id"
                  class="team-sheet-match"
                  @click="goToMatch(m.id)"
                >
                  <span class="team-sheet-match-date">{{ m.date }} · {{ m.time }}</span>
                  <span class="team-sheet-match-teams">
                    <span :class="{ 'team-sheet-match-em': isHome(m) }">{{ m.home_team.name }}</span>
                    <span class="team-sheet-match-vs"> — </span>
                    <span :class="{ 'team-sheet-match-em': !isHome(m) }">{{ m.away_team.name }}</span>
                  </span>
                </li>
              </ul>
              <p v-else class="team-sheet-muted">Нет ближайших матчей в окне расписания</p>
            </section>

            <section v-if="metrics" class="team-sheet-section">
              <h3 class="team-sheet-h3">Ключевые метрики</h3>
              <div class="team-sheet-metrics">
                <div class="team-sheet-metric">
                  <span class="team-sheet-metric-label">Место в таблице</span>
                  <span class="team-sheet-metric-val">{{ metrics.position || '—' }}</span>
                </div>
                <div class="team-sheet-metric">
                  <span class="team-sheet-metric-label">Очки</span>
                  <span class="team-sheet-metric-val">{{ metrics.points }}</span>
                </div>
                <div class="team-sheet-metric">
                  <span class="team-sheet-metric-label">СРТ</span>
                  <span class="team-sheet-metric-val">{{ formatNum(metrics.srt) }}</span>
                </div>
                <div class="team-sheet-metric">
                  <span class="team-sheet-metric-label">xG / xGA</span>
                  <span class="team-sheet-metric-val">{{ formatNum(metrics.xg) }} / {{ formatNum(metrics.xga) }}</span>
                </div>
                <div class="team-sheet-metric">
                  <span class="team-sheet-metric-label">ЖК (ср. за матч)</span>
                  <span class="team-sheet-metric-val">{{ formatNum(metrics.yellowAvg) }}</span>
                </div>
                <div class="team-sheet-metric">
                  <span class="team-sheet-metric-label">Угловые (ср. за матч)</span>
                  <span class="team-sheet-metric-val">{{ formatNum(metrics.cornersAvg) }}</span>
                </div>
              </div>
            </section>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import type { TeamShort, Match } from '../api'

export interface TeamProfileMetrics {
  position: number
  points: number
  srt: number
  xg: number
  xga: number
  yellowAvg: number
  cornersAvg: number
}

const props = defineProps<{
  open: boolean
  team: TeamShort | null
  leagueId: number
  leagueName: string
  metrics: TeamProfileMetrics | null
  upcomingMatches: Match[]
  loadingMatches: boolean
  matchesError: string | null
}>()

const emit = defineEmits<{ close: [] }>()

const router = useRouter()
const titleId = 'team-profile-sheet-title'

function isHome(m: Match): boolean {
  return props.team ? m.home_team.id === props.team.id : false
}

function goToMatch(matchId: number) {
  router.push(`/schedule/${props.leagueId}/match/${matchId}`)
  emit('close')
}

function formatNum(n: number): string {
  if (n === undefined || n === null || Number.isNaN(n)) return '—'
  return Number.isInteger(n) ? String(n) : n.toFixed(2)
}

let _prevHtmlOverflow = ''
let _prevBodyOverflow = ''

watch(
  () => [props.open, props.team] as const,
  ([open, team]) => {
    if (typeof document === 'undefined') return
    if (open && team) {
      _prevHtmlOverflow = document.documentElement.style.overflow
      _prevBodyOverflow = document.body.style.overflow
      document.documentElement.style.overflow = 'hidden'
      document.body.style.overflow = 'hidden'
    } else {
      document.documentElement.style.overflow = _prevHtmlOverflow
      document.body.style.overflow = _prevBodyOverflow
    }
  },
)

onUnmounted(() => {
  if (typeof document === 'undefined') return
  document.documentElement.style.overflow = _prevHtmlOverflow
  document.body.style.overflow = _prevBodyOverflow
})
</script>

<style scoped>
.team-sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 205;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  overscroll-behavior: none;
}

.team-sheet-panel {
  width: 100%;
  max-width: 480px;
  max-height: min(88vh, 640px);
  overflow-y: auto;
  touch-action: pan-y;
  overscroll-behavior: contain;
  background: var(--card);
  border-radius: 20px 20px 0 0;
  padding: 8px 16px calc(24px + var(--bottom-nav-current-height) + env(safe-area-inset-bottom));
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.12);
}

.team-sheet-grab {
  width: 36px;
  height: 4px;
  border-radius: 2px;
  background: var(--border);
  margin: 4px auto 12px;
}

.team-sheet-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}

.team-sheet-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.team-sheet-logo {
  width: 48px;
  height: 48px;
  object-fit: contain;
  flex-shrink: 0;
}

.team-sheet-logo-fallback {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
  flex-shrink: 0;
}

.team-sheet-titles {
  min-width: 0;
}

.team-sheet-name {
  margin: 0;
  color: #000;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 20px;
  font-weight: 700;
  line-height: 24px;
}

.team-sheet-sub {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 18px;
}

.team-sheet-close {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  font-size: 28px;
  line-height: 1;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 8px;
}

.team-sheet-close:active {
  opacity: 0.7;
}

.team-sheet-section {
  margin-bottom: 20px;
}

.team-sheet-h3 {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 600;
  color: #000;
}

.team-sheet-muted {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.team-sheet-error {
  margin: 0;
  color: var(--danger);
  font-size: 14px;
}

.team-sheet-matches {
  list-style: none;
  margin: 0;
  padding: 0;
}

.team-sheet-match {
  padding: 12px;
  border-radius: var(--radius);
  background: var(--bg);
  margin-bottom: 8px;
  cursor: pointer;
}

.team-sheet-match:last-child {
  margin-bottom: 0;
}

.team-sheet-match:active {
  opacity: 0.9;
}

.team-sheet-match-date {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.team-sheet-match-teams {
  font-size: 15px;
  font-weight: 500;
  color: #222;
}

.team-sheet-match-em {
  color: var(--primary);
  font-weight: 600;
}

.team-sheet-metrics {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.team-sheet-metric {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 10px 12px;
  background: var(--bg);
  border-radius: var(--radius);
}

.team-sheet-metric-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.team-sheet-metric-val {
  font-size: 15px;
  font-weight: 600;
  color: #222;
  text-align: right;
}

.sheet-fade-enter-active,
.sheet-fade-leave-active {
  transition: opacity 0.2s ease;
}

.sheet-fade-enter-from,
.sheet-fade-leave-to {
  opacity: 0;
}

</style>
