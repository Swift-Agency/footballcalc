<template>
  <div class="page">
    <template v-if="league">
      <!-- WC-specific header -->
      <div v-if="league.key === 'world_cup'" class="wc-cover">
        <div class="wc-cover-inner">
          <img
            v-if="getLeagueHeaderLogo(league)"
            :src="getLeagueHeaderLogo(league)!"
            alt=""
            class="wc-cover-trophy"
          />
          <div class="wc-cover-title">{{ league.name }}</div>
          <div class="wc-cover-sub">11 июня — 19 июля 2026</div>
        </div>
      </div>
      <LeagueHeader
        v-else
        :key="league.id"
        :name="league.name"
        :logo-url="getLeagueHeaderLogo(league)"
        :subtitle="formatSeasonSubtitle(league.season)"
      />
      <VenueFilter v-model="venue" />

      <QuotaBanner />

      <nav class="league-section-tabs" aria-label="Разделы лиги">
        <button
          v-for="tab in mainTabs"
          :key="tab.id"
          type="button"
          :class="['league-section-tab', { 'league-section-tab--active': activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div v-if="!loading">
        <!-- Standings: grouped (WC) or flat -->
        <template v-if="activeTab === 'standings'">
          <!-- Grouped standings -->
          <template v-if="league.has_groups && standingsGroups.length">
            <div
              v-for="group in standingsGroups"
              :key="group.name"
              class="card group-card"
            >
              <div class="section-head">
                <h3 class="card-section-title">{{ group.name }}</h3>
              </div>
              <SortableTable
                :columns="standingsColumns"
                :data="group.rows"
                default-sort-key="points"
                default-sort-dir="desc"
                :row-key="(r: any) => group.name + '-' + r.team.id"
                row-clickable
                @row-click="onTableRowClick"
              >
                <template #team="{ row, index }">
                  <div class="team-cell team-cell--standings">
                    <span class="pos-badge" :class="getZoneClass(index + 1)">{{ index + 1 }}</span>
                    <img
                      v-if="row.team.logo_url"
                      :src="row.team.logo_url"
                      :alt="row.team.name"
                      class="team-logo-sm-img"
                      @error="onTeamLogoError"
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
          </template>

          <!-- Flat standings -->
          <div class="card" v-else>
            <div class="section-head">
              <h3 class="card-section-title">Турнирная таблица</h3>
              <button type="button" class="info-btn" aria-label="Справка" @click="infoOpen = true">
                <img :src="infoIconSrc" alt="" width="15" height="15" />
              </button>
            </div>
            <SortableTable
              :columns="standingsColumns"
              :data="standings"
              default-sort-key="points"
              default-sort-dir="desc"
              :row-key="(r: any) => r.team.id"
              row-clickable
              @row-click="onTableRowClick"
            >
              <template #team="{ row, index }">
                <div class="team-cell team-cell--standings">
                  <span class="pos-badge" :class="getZoneClass(index + 1)">{{ index + 1 }}</span>
                  <img
                    v-if="row.team.logo_url"
                    :src="row.team.logo_url"
                    :alt="row.team.name"
                    class="team-logo-sm-img"
                    @error="onTeamLogoError"
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
        </template>

        <!-- Stats / Smallmarkets / xG (flat, same as before) -->
        <div class="card" v-else>
          <div class="section-head">
            <h3 class="card-section-title">{{ currentSectionTitle }}</h3>
            <button type="button" class="info-btn" aria-label="Справка по колонкам" @click="infoOpen = true">
              <img :src="infoIconSrc" alt="" width="15" height="15" />
            </button>
          </div>

          <SortableTable
            v-if="activeTab === 'stats'"
            :columns="advancedColumns"
            :data="advancedStats"
            default-sort-key="srt"
            default-sort-dir="desc"
            :row-key="(r: any) => 'adv-' + r.team.id"
            row-clickable
            @row-click="onTableRowClick"
          >
            <template #team="{ row, index }">
              <div class="team-cell team-cell--standings">
                <span class="pos-badge" :class="getZoneClass(index + 1)">{{ index + 1 }}</span>
                <img
                  v-if="row.team.logo_url"
                  :src="row.team.logo_url"
                  :alt="row.team.name"
                  class="team-logo-sm-img"
                  @error="onTeamLogoError"
                />
                <div v-else class="team-logo-sm">{{ row.team.name.charAt(0) }}</div>
                <span class="team-name-text" :title="row.team.name">{{ row.team.name }}</span>
              </div>
            </template>
            <template #obz_pct="{ value }">{{ value }}%</template>
          </SortableTable>

          <SortableTable
            v-else-if="activeTab === 'smallmarkets'"
            :columns="mergedSmColumns"
            :data="mergedSmallMarkets"
            default-sort-key="yellow_cards"
            default-sort-dir="desc"
            :row-key="(r: any) => 'sm-' + r.team.id"
            row-clickable
            @row-click="onTableRowClick"
          >
            <template #team="{ row, index }">
              <div class="team-cell team-cell--standings">
                <span class="pos-badge" :class="getZoneClass(index + 1)">{{ index + 1 }}</span>
                <img
                  v-if="row.team.logo_url"
                  :src="row.team.logo_url"
                  :alt="row.team.name"
                  class="team-logo-sm-img"
                  @error="onTeamLogoError"
                />
                <div v-else class="team-logo-sm">{{ row.team.name.charAt(0) }}</div>
                <span class="team-name-text" :title="row.team.name">{{ row.team.name }}</span>
              </div>
            </template>
          </SortableTable>

          <div v-else-if="activeTab === 'xg' && xgLoading" class="xg-loading">
            Загрузка xG…
          </div>

          <SortableTable
            v-else-if="activeTab === 'xg'"
            :columns="xgColumns"
            :data="xgStats"
            default-sort-key="delta_g"
            default-sort-dir="desc"
            :row-key="(r: any) => 'xg-' + r.team.id"
            row-clickable
            @row-click="onTableRowClick"
          >
            <template #team="{ row, index }">
              <div class="team-cell team-cell--standings">
                <span class="pos-badge" :class="getZoneClass(index + 1)">{{ index + 1 }}</span>
                <img
                  v-if="row.team.logo_url"
                  :src="row.team.logo_url"
                  :alt="row.team.name"
                  class="team-logo-sm-img"
                  @error="onTeamLogoError"
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
      </div>

      <ColumnInfoModal
        :open="infoOpen"
        :title="infoModalContent.title"
        :lines="infoModalContent.lines"
        @close="infoOpen = false"
      />
    </template>

    <p v-else-if="loading" class="loading">Загрузка...</p>
    <p v-else class="loading">Лига не найдена</p>
  </div>

  <PaywallSheet :open="xgPaywallOpen" @close="xgPaywallOpen = false" />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getLeagues,
  getStandings,
  getSmallMarkets,
  getXgStats,
  getAdvancedStats,
  isQuotaExhausted,
  isAuthRequired,
  type League,
  type StandingRow,
  type StandingGroup,
  type SmallMarketMetric,
  type SmallMarketRow,
  type XgRow,
  type VenueType,
  type AdvancedStatsRow,
  type TeamShort,
} from '../api'
import { getLeagueHeaderLogo } from '../leagueLogos'
import LeagueHeader from '../components/LeagueHeader.vue'
import VenueFilter from '../components/VenueFilter.vue'
import SortableTable from '../components/SortableTable.vue'
import ColumnInfoModal, { type InfoLine } from '../components/ColumnInfoModal.vue'
import {
  STANDINGS_INFO_LINES,
  SUMMARY_INFO_LINES,
  SMALLMARKETS_INFO_LINES,
  XG_INFO_LINES,
} from '../columnInfoLines'
import PaywallSheet from '../components/PaywallSheet.vue'
import QuotaBanner from '../components/QuotaBanner.vue'
import { refreshBillingProfile } from '../composables/useBillingProfile'
import infoIconSrc from '../assets/info-icon.svg'

const props = defineProps<{ id: string }>()
const router = useRouter()
const league = ref<League | null>(null)
const loading = ref(true)
const venue = ref<VenueType>('all')
const standings = ref<StandingRow[]>([])
const standingsGroups = ref<StandingGroup[]>([])
const xgStats = ref<XgRow[]>([])
const advancedStats = ref<AdvancedStatsRow[]>([])
const smallMarketRows = ref<Record<SmallMarketMetric, SmallMarketRow[]>>({
  yellow_cards: [],
  corners: [],
  shots_on_target: [],
  shots_total: [],
  fouls: [],
  offsides: [],
})

type MainTab = 'standings' | 'stats' | 'smallmarkets' | 'xg'

const activeTab = ref<MainTab>('standings')
const infoOpen = ref(false)
const xgLoaded = ref(false)
const xgLoading = ref(false)
const xgPaywallOpen = ref(false)

const mainTabs: { id: MainTab; label: string }[] = [
  { id: 'standings', label: 'Таблица' },
  { id: 'stats', label: 'Статистика' },
  { id: 'smallmarkets', label: 'Смоллмаркеты' },
  { id: 'xg', label: 'xG' },
]

const sectionTitles: Record<MainTab, string> = {
  standings: 'Турнирная таблица',
  stats: 'Статистика',
  smallmarkets: 'Смоллмаркеты',
  xg: 'Expected Goals (xG)',
}

const currentSectionTitle = computed(() => sectionTitles[activeTab.value])

const SM_METRICS: SmallMarketMetric[] = [
  'yellow_cards',
  'corners',
  'shots_on_target',
  'shots_total',
  'fouls',
  'offsides',
]

/** Merged grid: one numeric per metric using `srt` from each small-market response (see loadData). */
type MergedSmallMarketRow = {
  team: SmallMarketRow['team']
  yellow_cards: number
  corners: number
  shots_on_target: number
  shots_total: number
  fouls: number
  offsides: number
}

function mergeSmallMarkets(rec: Record<SmallMarketMetric, SmallMarketRow[]>): MergedSmallMarketRow[] {
  const base = rec.yellow_cards
  if (!base.length) return []
  return base.map((row) => {
    const id = row.team.id
    return {
      team: row.team,
      yellow_cards: row.srt,
      corners: pickSrt(rec.corners, id),
      shots_on_target: pickSrt(rec.shots_on_target, id),
      shots_total: pickSrt(rec.shots_total, id),
      fouls: pickSrt(rec.fouls, id),
      offsides: pickSrt(rec.offsides, id),
    }
  })
}

function pickSrt(rows: SmallMarketRow[], teamId: number): number {
  return rows.find((r) => r.team.id === teamId)?.srt ?? 0
}

const mergedSmallMarkets = computed(() => mergeSmallMarkets(smallMarketRows.value))

const standingsColumns = [
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

const advancedColumns = [
  { key: 'team', label: 'Команда', sortable: false, align: 'left' as const, sticky: true, width: '42%' },
  { key: 'srt', label: 'СРТ', width: '11%' },
  { key: 'srt1', label: 'СРТ1', width: '11%' },
  { key: 'srt2', label: 'СРТ2', width: '11%' },
  { key: 'obz_pct', label: 'ОБЗ%', width: '12%' },
  { key: 'matches', label: 'Матчи', width: '13%' },
]

const mergedSmColumns = [
  { key: 'team', label: 'Команда', sortable: false, align: 'left' as const, sticky: true, width: '42%' },
  { key: 'yellow_cards', label: 'ЖК', width: '9%' },
  { key: 'corners', label: 'УГЛ', width: '9%' },
  { key: 'shots_on_target', label: 'УС', width: '10%' },
  { key: 'shots_total', label: 'УД', width: '10%' },
  { key: 'fouls', label: 'Ф', width: '10%' },
  { key: 'offsides', label: 'ОФС', width: '10%' },
]

const xgColumns = [
  { key: 'team', label: 'Команда', sortable: false, align: 'left' as const, sticky: true, width: '42%' },
  { key: 'xg', label: 'XG', width: '12%' },
  { key: 'xga', label: 'XGA', width: '12%' },
  { key: 'delta_g', label: 'ΔG', width: '11%' },
  { key: 'delta_ga', label: 'ΔGA', width: '11%' },
  { key: 'matches', label: 'Матчи', width: '12%' },
]

const INFO_BY_TAB: Record<MainTab, { title: string; lines: InfoLine[] }> = {
  standings: {
    title: 'Турнирная таблица',
    lines: STANDINGS_INFO_LINES,
  },
  stats: {
    title: 'Статистика',
    lines: SUMMARY_INFO_LINES,
  },
  smallmarkets: {
    title: 'Смоллмаркеты',
    lines: SMALLMARKETS_INFO_LINES,
  },
  xg: {
    title: 'Expected Goals (xG)',
    lines: XG_INFO_LINES,
  },
}

const infoModalContent = computed(() => INFO_BY_TAB[activeTab.value])

function formatSeasonSubtitle(season?: number | null): string | undefined {
  if (!season) return undefined
  return `Сезон ${season}/${season + 1}`
}

function getZoneClass(position: number): string {
  if (position <= 4) return 'zone-cl'
  if (position === 5) return 'zone-el'
  if (position >= 18) return 'zone-relegation'
  return ''
}

async function loadLeagueInfo() {
  const all = await getLeagues()
  league.value = all.find((l) => l.id === Number(props.id)) || null
}

async function loadData() {
  const leagueId = Number(props.id)
  const v = venue.value
  loading.value = true
  xgLoaded.value = false
  xgStats.value = []
  try {
    const smResults = await Promise.all(SM_METRICS.map((m) => getSmallMarkets(leagueId, m, v)))
    const smRecord = {} as Record<SmallMarketMetric, SmallMarketRow[]>
    SM_METRICS.forEach((m, i) => {
      smRecord[m] = smResults[i] ?? []
    })

    const [standingsResp, advRows] = await Promise.all([
      getStandings(leagueId, v),
      getAdvancedStats(leagueId, v),
    ])

    if (standingsResp.groups) {
      standingsGroups.value = standingsResp.groups
      standings.value = standingsResp.groups.flatMap((g) => g.rows)
    } else {
      standingsGroups.value = []
      standings.value = standingsResp.rows ?? []
    }
    advancedStats.value = advRows
    smallMarketRows.value = smRecord
  } finally {
    loading.value = false
  }
}

async function loadXgData() {
  if (xgLoaded.value) return
  xgLoading.value = true
  try {
    const rows = await getXgStats(Number(props.id), venue.value)
    xgStats.value = rows
    xgLoaded.value = true
    await refreshBillingProfile()
  } catch (err: unknown) {
    if (isQuotaExhausted(err) || isAuthRequired(err)) {
      xgPaywallOpen.value = true
      await refreshBillingProfile()
    } else {
      console.error('[LeagueDetail] xG load failed:', err)
    }
  } finally {
    xgLoading.value = false
  }
}

watch(
  () => venue.value,
  () => {
    loadData()
    if (activeTab.value === 'xg') {
      xgLoaded.value = false
      xgStats.value = []
      loadXgData()
    }
  },
)

watch(
  () => props.id,
  async () => {
    await loadLeagueInfo()
    await loadData()
  },
)

watch(
  () => activeTab.value,
  (tab) => {
    if (tab === 'xg' && !xgLoaded.value) {
      loadXgData()
    }
  },
)

function onTeamLogoError(e: Event) {
  ;(e.target as HTMLImageElement).style.display = 'none'
}

function onTableRowClick(row: { team: TeamShort }) {
  const team = row.team
  if (!team) return
  router.push(`/leagues/${props.id}/team/${team.id}`)
}

onMounted(async () => {
  try {
    await loadLeagueInfo()
    await loadData()
  } catch (err) {
    console.error('[LeagueDetail] error loading leagues:', err)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.wc-cover {
  background: linear-gradient(135deg, #1a3c6e 0%, #0d2345 100%);
  box-sizing: border-box;
  padding: calc(var(--cover-top-padding) + var(--app-safe-top) + var(--header-title-offset)) 20px 24px;
  text-align: center;
}

.wc-cover-trophy {
  display: block;
  width: auto;
  height: 72px;
  margin: 0 auto 8px;
  object-fit: contain;
}

.wc-cover-title {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 4px;
}

.wc-cover-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.group-card {
  margin-bottom: 8px;
}

.league-section-tabs {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  padding: 8px 12px 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.league-section-tab {
  flex: 0 0 auto;
  border: none;
  background: none;
  padding: 8px 10px 10px;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 15px;
  font-weight: 500;
  line-height: 20px;
  color: var(--text-secondary);
  cursor: pointer;
  position: relative;
  white-space: nowrap;
}

.league-section-tab--active {
  color: var(--primary);
  font-weight: 600;
}

.league-section-tab--active::after {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 2px;
  height: 2px;
  border-radius: 1px;
  background: var(--primary);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  padding: 22px 24px 12px 24px;
}

.card-section-title {
  margin: 0;
  padding: 2px 0 0;
  color: #000;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 18px;
  font-weight: 600;
  line-height: 22px;
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

.team-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
}

.team-cell--standings {
  gap: 9px;
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
  font-weight: 500;
  line-height: 22px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}

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
  background: #9ca3af;
  flex-shrink: 0;
}

.pos-badge.zone-cl {
  background: #2c3ec4;
}

.pos-badge.zone-el {
  background: #ff5f5f;
}

.pos-badge.zone-relegation {
  background: #ff5f5f;
}

.positive {
  color: var(--success);
  font-weight: 600;
}

.negative {
  color: var(--danger);
  font-weight: 600;
}

</style>
