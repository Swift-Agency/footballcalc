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

    <div class="card" v-if="!loading">
      <h3 class="section-title">Турнирная таблица</h3>
      <SortableTable
        :columns="columns"
        :data="standings"
        default-sort-key="points"
        default-sort-dir="desc"
        :row-key="(r: any) => r.team.id"
        :row-class="getRowClass"
      >
        <template #team="{ row, index }">
          <div class="team-cell">
            <span class="pos-badge" :class="getZoneClass(index + 1)">
              {{ index + 1 }}
            </span>
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
        <template #goal_difference="{ value }">
          <span :class="value > 0 ? 'positive' : value < 0 ? 'negative' : ''">
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
  getStandings,
  getLeagues,
  flattenStandings,
  type StandingRow,
  type League,
  type VenueType,
} from '../api'
import { getLeagueHeaderLogo } from '../leagueLogos'
import LeagueHeader from '../components/LeagueHeader.vue'
import VenueFilter from '../components/VenueFilter.vue'
import SortableTable from '../components/SortableTable.vue'

const props = defineProps<{ id: string }>()
const league = ref<League | null>(null)
const standings = ref<StandingRow[]>([])
const venue = ref<VenueType>('all')
const loading = ref(true)

function formatSeasonSubtitle(season?: number | null): string | undefined {
  if (!season) return undefined
  return `Сезон ${season}/${season + 1}`
}

const columns = [
  { key: 'team', label: 'Команда', sortable: false, align: 'left' as const, sticky: true, width: '42%' },
  { key: 'played', label: 'И', width: '7%' },
  { key: 'won', label: 'В', width: '7%' },
  { key: 'drawn', label: 'Н', width: '7%' },
  { key: 'lost', label: 'П', width: '7%' },
  { key: 'goals_for', label: 'З', width: '7%' },
  { key: 'goals_against', label: 'ПР', width: '7%' },
  { key: 'goal_difference', label: '+/-', width: '7%' },
  { key: 'points', label: 'О', width: '8%' },
]

function getZoneClass(position: number): string {
  if (position <= 4) return 'zone-cl'
  if (position === 5) return 'zone-el'
  if (position >= 18) return 'zone-relegation'
  return ''
}

function getRowClass(_row: any, idx: number): string {
  return idx === 0 ? 'standings-row-first' : ''
}

function onTeamLogoError(e: Event, team: any) {
  console.warn('[Standings] team logo failed:', team.id, team.name_en, (e.target as HTMLImageElement).src)
  ;(e.target as HTMLImageElement).style.display = 'none'
}

async function loadData() {
  loading.value = true
  console.info('[Standings] loadData leagueId=%s venue=%s', props.id, venue.value)
  try {
    standings.value = flattenStandings(await getStandings(Number(props.id), venue.value))
    console.info('[Standings] loaded %d rows', standings.value.length)
  } catch (err) {
    console.error('[Standings] error:', err)
  } finally {
    loading.value = false
  }
}

watch(venue, () => {
  console.debug('[Standings] venue changed →', venue.value)
  loadData()
})

onMounted(async () => {
  console.info('[Standings] mounted id=%s', props.id)
  try {
    const all = await getLeagues()
    league.value = all.find((l) => l.id === Number(props.id)) || null
  } catch (err) {
    console.error('[Standings] failed to load league info:', err)
  }
  await loadData()
})
</script>

<style scoped>
.section-title {
  padding: 24px 0 6px 23px;
  color: #000;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 18px;
  font-style: normal;
  font-weight: 600;
  line-height: 22px;
}

/* First row: champion-style gradient */
.standings-row-first td {
  background: linear-gradient(180deg, rgba(55, 255, 145, 0.26) 0%, rgba(255, 255, 255, 0.98) 100%) !important;
}

.standings-row-first td.sticky-col {
  background: linear-gradient(180deg, rgba(55, 255, 145, 0.26) 0%, rgba(255, 255, 255, 0.98) 100%) !important;
}

/* Position badge: 16x16 circle, zone colors, white number */
.pos-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 8px;
  font-size: 9px;
  font-weight: 700;
  color: white;
  background: #9CA3AF;
  flex-shrink: 0;
}

.pos-badge.zone-cl {
  background: #2CC485;
}

.pos-badge.zone-el {
  background: #0373FF;
}

.pos-badge.zone-relegation {
  background: #EF4444;
}

.team-cell {
  display: flex;
  align-items: center;
  gap: 9px;
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
