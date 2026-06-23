<template>
  <div class="page">
    <LeagueHeader
      v-if="league"
      :key="league.id"
      :name="league.name"
      :logo-url="getLeagueHeaderLogo(league)"
      :subtitle="formatSeasonSubtitle(league.season)"
    />
    <VenueFilter v-model="venue" />

    <!-- Advanced Stats -->
    <div class="card" v-if="!loading">
      <h3 class="section-title">Сводка</h3>
      <SortableTable
        :columns="advancedColumns"
        :data="advancedStats"
        default-sort-key="srt"
        default-sort-dir="desc"
        :row-key="(r: any) => 'adv-' + r.team.id"
      >
        <template #team="{ row }">
          <div class="team-cell">
            <img
              v-if="row.team.logo_url"
              :src="row.team.logo_url"
              :alt="row.team.name"
              class="team-logo-sm-img"
              @error="(e) => onTeamLogoError(e, row.team)"
            />
            <div v-else class="team-logo-sm">{{ row.team.name.charAt(0) }}</div>
            <span class="team-name-text" :title="row.team.name">{{ row.team.name }}</span>
          </div>
        </template>
        <template #obz_pct="{ value }">{{ value }}%</template>
      </SortableTable>
    </div>

    <!-- Smallmarkets -->
    <div class="card" v-if="!loading">
      <h3 class="section-title">Смоллмаркет</h3>
      <div class="metric-tabs">
        <button
          v-for="m in metricOptions"
          :key="m.value"
          :class="{ active: currentMetric === m.value }"
          @click="switchMetric(m.value)"
        >
          {{ m.label }}
        </button>
      </div>
      <SortableTable
        :columns="smallMarketColumns"
        :data="smallMarkets"
        default-sort-key="srt"
        default-sort-dir="desc"
        :row-key="(r: any) => 'sm-' + r.team.id"
      >
        <template #team="{ row }">
          <div class="team-cell">
            <img
              v-if="row.team.logo_url"
              :src="row.team.logo_url"
              :alt="row.team.name"
              class="team-logo-sm-img"
              @error="(e) => onTeamLogoError(e, row.team)"
            />
            <div v-else class="team-logo-sm">{{ row.team.name.charAt(0) }}</div>
            <span class="team-name-text" :title="row.team.name">{{ row.team.name }}</span>
          </div>
        </template>
      </SortableTable>
    </div>

    <!-- xG Stats -->
    <div class="card" v-if="!loading">
      <h3 class="section-title">Expected Goals (xG)</h3>
      <SortableTable
        :columns="xgColumns"
        :data="xgStats"
        default-sort-key="delta_g"
        default-sort-dir="desc"
        :row-key="(r: any) => 'xg-' + r.team.id"
      >
        <template #team="{ row }">
          <div class="team-cell">
            <img
              v-if="row.team.logo_url"
              :src="row.team.logo_url"
              :alt="row.team.name"
              class="team-logo-sm-img"
              @error="(e) => onTeamLogoError(e, row.team)"
            />
            <div v-else class="team-logo-sm">{{ row.team.name.charAt(0) }}</div>
            <span class="team-name-text" :title="row.team.name">{{ row.team.name }}</span>
          </div>
        </template>
        <template #delta_g="{ value }">
          <span :class="value > 0 ? 'positive' : value < 0 ? 'negative' : ''">
            {{ value > 0 ? '+' : '' }}{{ value }}
          </span>
        </template>
        <template #delta_ga="{ value }">
          <span :class="value < 0 ? 'positive' : value > 0 ? 'negative' : ''">
            {{ value > 0 ? '+' : '' }}{{ value }}
          </span>
        </template>
      </SortableTable>
    </div>

    <p v-if="loading" class="loading">Загрузка...</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import {
  getLeagues, getAdvancedStats, getSmallMarkets, getXgStats,
  type League, type VenueType, type AdvancedStatsRow,
  type SmallMarketRow, type XgRow, type SmallMarketMetric,
} from '../api'
import { getLeagueHeaderLogo } from '../leagueLogos'
import LeagueHeader from '../components/LeagueHeader.vue'
import VenueFilter from '../components/VenueFilter.vue'
import SortableTable from '../components/SortableTable.vue'

const props = defineProps<{ id: string }>()
const league = ref<League | null>(null)
const venue = ref<VenueType>('all')
const loading = ref(true)

function formatSeasonSubtitle(season?: number | null): string | undefined {
  if (!season) return undefined
  return `Сезон ${season}/${season + 1}`
}

const advancedStats = ref<AdvancedStatsRow[]>([])
const smallMarkets = ref<SmallMarketRow[]>([])
const xgStats = ref<XgRow[]>([])
const currentMetric = ref<SmallMarketMetric>('yellow_cards')

const advancedColumns = [
  { key: 'team', label: 'Команда', sortable: false, align: 'left' as const, sticky: true, width: '42%' },
  { key: 'srt', label: 'СРТ', width: '12%' },
  { key: 'srt1', label: 'СРТ1', width: '12%' },
  { key: 'srt2', label: 'СРТ2', width: '12%' },
  { key: 'obz_pct', label: 'ОБЗ%', width: '11%' },
  { key: 'matches', label: 'Матчи', width: '11%' },
]

const smallMarketColumns = [
  { key: 'team', label: 'Команда', sortable: false, align: 'left' as const, sticky: true, width: '42%' },
  { key: 'matches', label: 'М', width: '14%' },
  { key: 'srt', label: 'СРТ', width: '14%' },
  { key: 'srt1', label: 'СРТ1', width: '15%' },
  { key: 'srt2', label: 'СРТ2', width: '15%' },
]

const xgColumns = [
  { key: 'team', label: 'Команда', sortable: false, align: 'left' as const, sticky: true, width: '42%' },
  { key: 'xg', label: 'XG', width: '12%' },
  { key: 'xga', label: 'XGA', width: '12%' },
  { key: 'delta_g', label: 'ΔG', width: '11%' },
  { key: 'delta_ga', label: 'ΔGA', width: '11%' },
  { key: 'matches', label: 'Матчи', width: '12%' },
]

const metricOptions: { value: SmallMarketMetric; label: string }[] = [
  { value: 'yellow_cards', label: 'ЖК' },
  { value: 'corners', label: 'Угловые' },
  { value: 'shots_on_target', label: 'В створ' },
  { value: 'shots_total', label: 'Удары' },
  { value: 'fouls', label: 'Фолы' },
  { value: 'offsides', label: 'Офсайды' },
]

function onTeamLogoError(e: Event, team: any) {
  console.warn('[Stats] team logo failed:', team.id, team.name_en, (e.target as HTMLImageElement).src)
  ;(e.target as HTMLImageElement).style.display = 'none'
}

async function switchMetric(m: SmallMarketMetric) {
  console.debug('[Stats] switchMetric →', m)
  currentMetric.value = m
  smallMarkets.value = await getSmallMarkets(Number(props.id), m, venue.value)
}

async function loadAll() {
  loading.value = true
  console.info('[Stats] loadAll leagueId=%s venue=%s', props.id, venue.value)
  try {
    const lid = Number(props.id)
    const [adv, sm, xg] = await Promise.all([
      getAdvancedStats(lid, venue.value),
      getSmallMarkets(lid, currentMetric.value, venue.value),
      getXgStats(lid, venue.value),
    ])
    advancedStats.value = adv
    smallMarkets.value = sm
    xgStats.value = xg
    console.info('[Stats] loaded adv=%d sm=%d xg=%d', adv.length, sm.length, xg.length)
  } catch (err) {
    console.error('[Stats] error loading stats:', err)
  } finally {
    loading.value = false
  }
}

watch(venue, () => {
  console.debug('[Stats] venue changed →', venue.value)
  loadAll()
})

onMounted(async () => {
  console.info('[Stats] mounted id=%s', props.id)
  try {
    const all = await getLeagues()
    league.value = all.find((l) => l.id === Number(props.id)) || null
  } catch (err) {
    console.error('[Stats] failed to load league info:', err)
  }
  await loadAll()
})
</script>

<style scoped>
.section-title {
  padding: 22px 0 15px 24px;
  color: #000;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 24px;
  font-style: normal;
  font-weight: 600;
  line-height: 22px;
}

.metric-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.metric-tabs button {
  padding: 6px 12px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
}

.metric-tabs button.active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.team-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.team-logo-sm-img {
  width: 24px;
  height: 24px;
  object-fit: contain;
  flex-shrink: 0;
}

.team-logo-sm {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: var(--primary);
  flex-shrink: 0;
}

.team-name-text {
  color: #222;
  text-align: left;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 16px;
  font-style: normal;
  font-weight: 500;
  line-height: 22px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}

.positive { color: var(--success); font-weight: 600; }
.negative { color: var(--danger); font-weight: 600; }
</style>
