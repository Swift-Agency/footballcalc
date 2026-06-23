<template>
  <div class="page team-page">
    <div v-if="loading" class="loading">Загрузка...</div>
    <div v-else-if="error" class="loading">{{ error }}</div>
    <template v-else-if="profile">
      <!-- Cover -->
      <div class="team-cover">
        <img
          v-if="profile.team.logo_url && !logoFailed"
          :src="profile.team.logo_url"
          :alt="profile.team.name"
          class="team-cover-logo"
          @error="logoFailed = true"
        />
        <div v-else class="team-cover-initial">{{ profile.team.name.charAt(0) }}</div>
        <h1 class="team-cover-name">{{ profile.team.name }}</h1>
      </div>

      <!-- Venue filter -->
      <VenueFilter v-model="venue" />

      <!-- Summary card -->
      <div class="card team-card">
        <div class="section-head">
          <h3 class="card-section-title">Сводка</h3>
          <button
            type="button"
            class="info-btn"
            aria-label="Справка по показателям"
            @click="summaryInfoOpen = true"
          >
            <img :src="infoIconSrc" alt="" width="15" height="15" />
          </button>
        </div>
        <div class="summary-grid">
          <div class="summary-col">
            <div class="summary-label">СРТ</div>
            <div class="summary-value">{{ profile.summary.srt.toFixed(2) }}</div>
          </div>
          <div class="summary-col">
            <div class="summary-label">СРТ1</div>
            <div class="summary-value">{{ profile.summary.srt1.toFixed(2) }}</div>
          </div>
          <div class="summary-col">
            <div class="summary-label">СРТ2</div>
            <div class="summary-value">{{ profile.summary.srt2.toFixed(2) }}</div>
          </div>
          <div class="summary-col">
            <div class="summary-label">ОБЗ%</div>
            <div class="summary-value">{{ profile.summary.obz_pct }}%</div>
          </div>
          <div class="summary-col">
            <div class="summary-label">Матчи</div>
            <div class="summary-value">{{ profile.summary.matches }}</div>
          </div>
        </div>
      </div>

      <!-- Smallmarkets card -->
      <div class="card team-card">
        <h3 class="card-section-title">Смоллмаркет</h3>
        <div class="metric-list">
          <div
            v-for="m in profile.smallmarkets"
            :key="m.metric"
            class="metric-row"
          >
            <span class="metric-label">{{ m.label }}</span>
            <div class="metric-values">
              <span class="metric-srt1">{{ m.srt1.toFixed(1) }}</span>
              <span class="metric-sep">/</span>
              <span class="metric-srt2">{{ m.srt2.toFixed(1) }}</span>
              <span class="metric-total">= {{ m.srt.toFixed(1) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- xG card (optional) -->
      <div class="card team-card" v-if="profile.xg && profile.xg.matches > 0">
        <h3 class="card-section-title">Expected Goals (xG)</h3>
        <div class="summary-grid">
          <div class="summary-col">
            <div class="summary-label">XG</div>
            <div class="summary-value">{{ profile.xg.xg.toFixed(2) }}</div>
          </div>
          <div class="summary-col">
            <div class="summary-label">XGA</div>
            <div class="summary-value">{{ profile.xg.xga.toFixed(2) }}</div>
          </div>
          <div class="summary-col">
            <div class="summary-label">ΔG</div>
            <div
              class="summary-value"
              :class="profile.xg.delta_g > 0 ? 'positive' : profile.xg.delta_g < 0 ? 'negative' : ''"
            >
              {{ profile.xg.delta_g > 0 ? '+' : '' }}{{ profile.xg.delta_g }}
            </div>
          </div>
          <div class="summary-col">
            <div class="summary-label">ΔGA</div>
            <div
              class="summary-value"
              :class="profile.xg.delta_ga < 0 ? 'positive' : profile.xg.delta_ga > 0 ? 'negative' : ''"
            >
              {{ profile.xg.delta_ga > 0 ? '+' : '' }}{{ profile.xg.delta_ga }}
            </div>
          </div>
          <div class="summary-col">
            <div class="summary-label">Матчи</div>
            <div class="summary-value">{{ profile.xg.matches }}</div>
          </div>
        </div>
      </div>
      <ColumnInfoModal
        :open="summaryInfoOpen"
        title="Сводка"
        :lines="SUMMARY_INFO_LINES"
        @close="summaryInfoOpen = false"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { getTeamProfile, type TeamProfileResponse, type VenueType } from '../api'
import VenueFilter from '../components/VenueFilter.vue'
import ColumnInfoModal from '../components/ColumnInfoModal.vue'
import { SUMMARY_INFO_LINES } from '../columnInfoLines'
import infoIconSrc from '../assets/info-icon.svg'

const props = defineProps<{ leagueId: string; teamId: string }>()

const loading = ref(true)
const error = ref<string | null>(null)
const profile = ref<TeamProfileResponse | null>(null)
const venue = ref<VenueType>('all')
const logoFailed = ref(false)
const summaryInfoOpen = ref(false)

async function load() {
  loading.value = true
  error.value = null
  logoFailed.value = false
  try {
    profile.value = await getTeamProfile(Number(props.leagueId), Number(props.teamId), venue.value)
  } catch (e: any) {
    error.value = 'Не удалось загрузить профиль команды'
    console.error('[TeamView] error:', e)
  } finally {
    loading.value = false
  }
}

watch(() => venue.value, load)

onMounted(() => {
  load()
})
</script>

<style scoped>
.team-page {
  padding-bottom: 24px;
}

.team-cover {
  background: linear-gradient(180deg, var(--primary-dark, #1a3c6e) 0%, var(--bg) 100%);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: calc(var(--cover-top-padding) + var(--app-safe-top) + var(--header-title-offset)) 20px 20px;
  gap: 10px;
}

.team-cover-logo {
  width: 72px;
  height: 72px;
  object-fit: contain;
  border-radius: 50%;
  background: #fff;
  padding: 4px;
}

.team-cover-initial {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--card);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
}

.team-cover-name {
  font-size: 22px;
  font-weight: 700;
  text-align: center;
  margin: 0;
}

.team-card {
  margin: 0 12px 12px;
  padding: 16px;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.card-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 14px;
}

.section-head .card-section-title {
  margin-bottom: 0;
}

.info-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
}

.info-btn:active {
  opacity: 0.7;
}

.summary-grid {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-col {
  flex: 1;
  min-width: 48px;
  text-align: center;
  background: var(--bg);
  border-radius: 8px;
  padding: 10px 6px;
}

.summary-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.summary-value {
  font-size: 16px;
  font-weight: 600;
}

.metric-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border, #e6e9ed);
}

.metric-row:last-child {
  border-bottom: none;
}

.metric-label {
  font-size: 14px;
  color: var(--text-primary);
}

.metric-values {
  display: flex;
  gap: 4px;
  align-items: center;
  font-size: 14px;
}

.metric-srt1 {
  font-weight: 600;
  color: var(--primary);
}

.metric-srt2 {
  font-weight: 600;
  color: var(--text-secondary);
}

.metric-sep {
  color: var(--text-secondary);
}

.metric-total {
  color: var(--text-secondary);
  font-size: 12px;
}

.positive { color: #22c55e; }
.negative { color: #ef4444; }
</style>
