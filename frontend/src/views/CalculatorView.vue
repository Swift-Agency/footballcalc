<template>
  <div class="page">
    <div class="leagues-page-header">
      <div class="leagues-page-header-inner">
        <h1>Калькулятор коэффициентов</h1>
      </div>
    </div>

    <QuotaBanner class="calculator-quota-banner" />

    <main class="calculator-content">
      <section class="team-picker-card">
        <div class="picker-row" @click="openPicker('home')">
          <span class="picker-label">Хозяева</span>
          <template v-if="homeTeam">
            <div class="team-chip">
              <img
                v-if="homeTeam.logo_url"
                :src="homeTeam.logo_url"
                :alt="homeTeam.name"
                class="team-logo"
              />
              <span v-else class="team-dot" />
              <span class="team-chip-name">{{ homeTeam.name }}</span>
            </div>
          </template>
          <template v-else>
            <span class="picker-placeholder">Выбор команды хозяев</span>
          </template>
        </div>

        <button class="swap-btn" type="button" @click.stop="swapTeams" aria-label="Поменять команды">
          ⇵
        </button>

        <div class="picker-divider" />

        <div class="picker-row" @click="openPicker('away')">
          <span class="picker-label">Гости</span>
          <template v-if="awayTeam">
            <div class="team-chip">
              <img
                v-if="awayTeam.logo_url"
                :src="awayTeam.logo_url"
                :alt="awayTeam.name"
                class="team-logo"
              />
              <span v-else class="team-dot" />
              <span class="team-chip-name">{{ awayTeam.name }}</span>
            </div>
          </template>
          <template v-else>
            <span class="picker-placeholder">
              {{ homeTeam ? 'Выбор команды гостей' : 'Сначала выберите хозяев' }}
            </span>
          </template>
        </div>
      </section>

      <button class="calculate-btn" :disabled="!canCalculate || calculating" @click="handleCalculate">
        {{ calculating ? 'Считаем...' : 'Рассчитать' }}
      </button>

      <p v-if="calculateError" class="calculate-error">{{ calculateError }}</p>

      <section v-if="result" class="result-sections">
        <article class="result-card">
          <h2 class="result-title">Исходы матча (1X2)</h2>
          <div class="result-table-head">
            <span>Событие</span>
            <span>Вероятность</span>
            <span>Коэффициент</span>
          </div>
          <div v-for="(row, idx) in result.main_outcomes" :key="`main-${idx}`" class="result-row">
            <div class="result-event">
              <span class="event-code">{{ row.event }}</span>
              <span v-if="row.subevent" class="event-sub">{{ row.subevent }}</span>
            </div>
            <span>{{ formatPercent(row.probability) }}</span>
            <span>{{ formatOdds(row.odds) }}</span>
          </div>
        </article>

        <article v-for="section in result.sections" :key="section.id" class="result-card">
          <h2 class="result-title">{{ section.title }}</h2>
          <div class="result-table-head">
            <span>Событие</span>
            <span>Вероятность</span>
            <span>Коэффициент</span>
          </div>
          <div v-for="(row, idx) in section.rows" :key="`${section.id}-${idx}`" class="result-row">
            <span class="event-code">{{ row.event }}</span>
            <span>{{ formatPercent(row.probability) }}</span>
            <span>{{ formatOdds(row.odds) }}</span>
          </div>
        </article>
      </section>
    </main>

    <Teleport to="body">
      <div
        v-if="sheetOpen"
        class="picker-overlay"
        aria-hidden="true"
        @click.self="closeSheet"
      />
      <div v-if="sheetOpen" class="picker-sheet" role="dialog" aria-modal="true" :aria-labelledby="sheetTitleId">
        <div class="picker-sheet-handle" />
        <header class="picker-sheet-header">
          <button
            v-if="sheetStep === 'teams'"
            type="button"
            class="picker-sheet-back"
            aria-label="Назад к лигам"
            @click="goBackInSheet"
          >
            ‹
          </button>
          <span v-else class="picker-sheet-back-spacer" />
          <h2 :id="sheetTitleId" class="picker-sheet-title">{{ sheetTitle }}</h2>
          <button type="button" class="picker-sheet-close" aria-label="Закрыть" @click="closeSheet">
            ×
          </button>
        </header>

        <div v-if="sheetStep === 'teams'" class="picker-search-wrap">
          <input
            v-model="teamSearchQuery"
            type="search"
            class="picker-search-input"
            placeholder="Поиск по команде"
            autocomplete="off"
          />
        </div>

        <div class="picker-sheet-body">
          <template v-if="sheetStep === 'leagues'">
            <p v-if="leaguesLoading" class="picker-muted">Загрузка лиг…</p>
            <p v-else-if="!pickerLeagues.length" class="picker-muted">Нет доступных лиг</p>
            <ul v-else class="picker-list" role="listbox">
              <li
                v-for="league in pickerLeagues"
                :key="league.id"
                class="picker-league-row"
                role="option"
                tabindex="0"
                @click="selectLeague(league)"
                @keydown.enter.prevent="selectLeague(league)"
              >
                <img
                  v-if="leagueLogoSrc(league)"
                  :src="leagueLogoSrc(league)!"
                  :alt="league.name"
                  class="picker-league-logo"
                  @error="onLeagueLogoError(league.id)"
                />
                <div v-else class="picker-league-fallback">{{ league.name.charAt(0) }}</div>
                <span class="picker-league-name">{{ league.name }}</span>
                <span class="picker-chevron">›</span>
              </li>
            </ul>
          </template>

          <template v-else>
            <p v-if="teamsLoading" class="picker-muted">Загрузка команд…</p>
            <p v-else-if="!filteredTeams.length" class="picker-muted">Нет команд по запросу</p>
            <ul v-else class="picker-list picker-list--teams" role="listbox">
              <li
                v-for="team in filteredTeams"
                :key="team.id"
                class="picker-team-row"
                role="option"
                tabindex="0"
                @click="selectTeamFromSheet(team)"
                @keydown.enter.prevent="selectTeamFromSheet(team)"
              >
                <img
                  v-if="team.logo_url"
                  :src="team.logo_url"
                  :alt="team.name"
                  class="team-logo"
                />
                <span v-else class="team-dot" />
                <span class="picker-team-name">
                  <template v-for="(seg, si) in teamNameSegments(team)" :key="`${team.id}-${si}`">
                    <strong v-if="seg.bold" class="team-option-match">{{ seg.text }}</strong>
                    <template v-else>{{ seg.text }}</template>
                  </template>
                </span>
              </li>
            </ul>
          </template>
        </div>
      </div>
    </Teleport>
  </div>

  <PaywallSheet :open="paywallOpen" :quota-override="lastQuota" @close="paywallOpen = false" />
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  calculateOdds,
  getLeagues,
  getStandings,
  flattenStandings,
  searchCalculatorTeams,
  isQuotaExhausted,
  isAuthRequired,
  getApiErrorPayload,
  type CalculatorResult,
  type League,
  type TeamShort,
  type UsageQuota,
} from '../api'
import { getLeagueListLogo } from '../leagueLogos'
import { sortLeaguesByDisplayOrder } from '../leagueOrder'
import { postAppEvent } from '../analytics'
import { getTelegram } from '../telegram'
import PaywallSheet from '../components/PaywallSheet.vue'
import QuotaBanner from '../components/QuotaBanner.vue'
import { refreshBillingProfile } from '../composables/useBillingProfile'

type TeamField = 'home' | 'away'
type SheetStep = 'leagues' | 'teams'

const sheetTitleId = 'calculator-picker-title'

const leagues = ref<League[]>([])
const leaguesLoading = ref(true)
const failedLeagueLogos = ref<Set<number>>(new Set())

const sheetOpen = ref(false)
const sheetField = ref<TeamField | null>(null)
const sheetStep = ref<SheetStep>('leagues')
const sheetLeague = ref<League | null>(null)
const teamsForSheet = ref<TeamShort[]>([])
const teamsLoading = ref(false)
const teamSearchQuery = ref('')

const homeTeam = ref<TeamShort | null>(null)
const awayTeam = ref<TeamShort | null>(null)
const calculating = ref(false)
const calculateError = ref<string | null>(null)
const result = ref<CalculatorResult | null>(null)

const canCalculate = computed(() => !!homeTeam.value && !!awayTeam.value)
const paywallOpen = ref(false)
const lastQuota = ref<UsageQuota | null>(null)

const pickerLeagues = computed(() =>
  sortLeaguesByDisplayOrder(leagues.value),
)

const sheetTitle = computed(() => {
  if (sheetStep.value === 'leagues') {
    return sheetField.value === 'home' ? 'Хозяева — выбор лиги' : 'Гости — выбор лиги'
  }
  if (!sheetLeague.value && sheetField.value === 'away' && homeTeam.value) {
    return 'Гости — та же лига, что у хозяев'
  }
  const name = sheetLeague.value?.name ?? 'Команды'
  return sheetField.value === 'home' ? `Хозяева — ${name}` : `Гости — ${name}`
})

const filteredTeams = computed(() => {
  const q = teamSearchQuery.value.trim().toLowerCase()
  if (!q) return teamsForSheet.value
  return teamsForSheet.value.filter((t) => {
    const n = t.name.toLowerCase()
    const e = t.name_en.toLowerCase()
    return n.includes(q) || e.includes(q)
  })
})

function leagueLogoSrc(league: League): string | null {
  if (failedLeagueLogos.value.has(league.id)) return null
  return getLeagueListLogo(league)
}

function onLeagueLogoError(leagueId: number) {
  failedLeagueLogos.value = new Set([...failedLeagueLogos.value, leagueId])
}

function lockBodyScroll(lock: boolean) {
  document.documentElement.style.overflow = lock ? 'hidden' : ''
  document.body.style.overflow = lock ? 'hidden' : ''
}

function closeSheet() {
  sheetOpen.value = false
  sheetField.value = null
  sheetStep.value = 'leagues'
  sheetLeague.value = null
  teamsForSheet.value = []
  teamSearchQuery.value = ''
  teamsLoading.value = false
  lockBodyScroll(false)
}

function goBackInSheet() {
  if (sheetField.value === 'away' && homeTeam.value) {
    closeSheet()
    return
  }
  if (sheetStep.value === 'teams') {
    teamSearchQuery.value = ''
    teamsForSheet.value = []
    sheetLeague.value = null
    sheetStep.value = 'leagues'
  }
}

async function openPicker(field: TeamField) {
  if (field === 'away' && !homeTeam.value) return

  sheetField.value = field
  teamSearchQuery.value = ''
  teamsForSheet.value = []
  sheetLeague.value = null
  lockBodyScroll(true)
  sheetOpen.value = true

  if (field === 'away' && homeTeam.value?.league_id != null) {
    if (!leagues.value.length) await loadLeagues()
    const hid = homeTeam.value.league_id
    const lg = leagues.value.find((l) => l.id === hid)
    if (lg) {
      sheetStep.value = 'teams'
      sheetLeague.value = lg
      await loadTeamsForLeague(hid)
      return
    }
    sheetStep.value = 'teams'
    sheetLeague.value = null
    await loadTeamsForLeague(hid)
    return
  }

  sheetStep.value = 'leagues'
  if (!leagues.value.length && !leaguesLoading.value) {
    await loadLeagues()
  }
}

async function loadLeagues() {
  leaguesLoading.value = true
  try {
    leagues.value = await getLeagues()
  } catch (err) {
    console.error('[CalculatorView] getLeagues failed:', err)
    leagues.value = []
  } finally {
    leaguesLoading.value = false
  }
}

async function selectLeague(league: League) {
  sheetStep.value = 'teams'
  sheetLeague.value = league
  teamSearchQuery.value = ''
  await loadTeamsForLeague(league.id)
}

async function loadTeamsForLeague(leagueId: number) {
  teamsLoading.value = true
  teamsForSheet.value = []
  try {
    const standings = flattenStandings(await getStandings(leagueId, 'all'))
    let teams = standings.map((row) => {
      const t = row.team
      return {
        ...t,
        league_id: t.league_id ?? leagueId,
      } as TeamShort
    })
    if (!teams.length) {
      teams = await searchCalculatorTeams('', { leagueId })
    }
    teams = teams.filter((t) => {
      if (sheetField.value === 'home' && awayTeam.value?.id === t.id) return false
      if (sheetField.value === 'away' && homeTeam.value?.id === t.id) return false
      return true
    })
    teamsForSheet.value = teams
  } catch (err) {
    console.error('[CalculatorView] load teams failed:', err)
    try {
      teamsForSheet.value = await searchCalculatorTeams('', { leagueId })
    } catch (e2) {
      teamsForSheet.value = []
    }
  } finally {
    teamsLoading.value = false
  }
}

function selectTeamFromSheet(team: TeamShort) {
  const field = sheetField.value
  if (!field) return

  if (field === 'home') {
    homeTeam.value = team
    if (awayTeam.value && awayTeam.value.league_id !== team.league_id) {
      awayTeam.value = null
    }
    closeSheet()
    return
  }

  awayTeam.value = team
  closeSheet()
}

/** Highlight search within team list */
function searchHighlightSegments(text: string, query: string): { text: string; bold: boolean }[] {
  const q = query.trim()
  if (!q || !text) return [{ text: text || '', bold: false }]
  const lower = text.toLowerCase()
  const ql = q.toLowerCase()
  if (!lower.includes(ql)) return [{ text, bold: false }]
  const out: { text: string; bold: boolean }[] = []
  let i = 0
  while (i < text.length) {
    const idx = lower.indexOf(ql, i)
    if (idx === -1) {
      out.push({ text: text.slice(i), bold: false })
      break
    }
    if (idx > i) out.push({ text: text.slice(i, idx), bold: false })
    out.push({ text: text.slice(idx, idx + q.length), bold: true })
    i = idx + q.length
  }
  return out
}

function teamNameSegments(team: TeamShort): { text: string; bold: boolean }[] {
  const q = teamSearchQuery.value.trim()
  if (!q) return [{ text: team.name, bold: false }]
  const fromName = searchHighlightSegments(team.name, q)
  if (fromName.some((s) => s.bold)) return fromName
  return searchHighlightSegments(team.name_en, q)
}

let _searchAnalyticsTimer: ReturnType<typeof setTimeout> | null = null
watch(teamSearchQuery, (q) => {
  if (_searchAnalyticsTimer) clearTimeout(_searchAnalyticsTimer)
  _searchAnalyticsTimer = setTimeout(() => {
    const t = q.trim()
    if (t.length >= 2) {
      const uid = getTelegram()?.initDataUnsafe?.user?.id
      postAppEvent(
        'search',
        { context: 'calculator', query: t },
        typeof uid === 'number' ? uid : undefined,
      )
    }
  }, 400)
})

function swapTeams() {
  const h = homeTeam.value
  const a = awayTeam.value
  if (!h && !a) return
  homeTeam.value = a
  awayTeam.value = h
}

async function handleCalculate() {
  if (!homeTeam.value || !awayTeam.value) return
  calculating.value = true
  calculateError.value = null
  try {
    result.value = await calculateOdds(homeTeam.value.id, awayTeam.value.id)
    await refreshBillingProfile()
  } catch (err: unknown) {
    result.value = null
    if (isQuotaExhausted(err) || isAuthRequired(err)) {
      const payload = getApiErrorPayload(err)
      if (payload && payload.remaining !== undefined) {
        lastQuota.value = {
          is_unlimited: false,
          weekly_limit: Number(payload.weekly_limit),
          used: Number(payload.used),
          remaining: Number(payload.remaining),
          resets_at: String(payload.resets_at ?? ''),
        }
      }
      paywallOpen.value = true
      await refreshBillingProfile()
    } else {
      const payload = getApiErrorPayload(err)
      const detail = payload?.message ?? payload?.detail
      calculateError.value =
        typeof detail === 'string'
          ? detail
          : 'Не удалось рассчитать коэффициенты. Попробуйте другие команды.'
    }
  } finally {
    calculating.value = false
  }
}

function formatPercent(value: number): string {
  return `${value.toFixed(1).replace('.', ',')}%`
}

function formatOdds(value: number): string {
  return value.toFixed(2).replace('.', ',')
}

watch([homeTeam, awayTeam], () => {
  result.value = null
  calculateError.value = null
})

onMounted(async () => {
  homeTeam.value = null
  awayTeam.value = null
  await loadLeagues()
})

onUnmounted(() => {
  lockBodyScroll(false)
})
</script>

<style scoped>
.calculator-quota-banner {
  margin-top: 10px;
}

.calculator-content {
  padding: 12px 8px 0;
}

.team-picker-card {
  position: relative;
  background: var(--card);
  border-radius: 24px;
  margin-bottom: 10px;
  overflow: hidden;
}

.picker-row {
  min-height: 64px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 10px 24px;
  cursor: pointer;
}

.picker-label {
  color: #aab2bd;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.3;
  margin-bottom: 2px;
}

.picker-placeholder {
  color: #a8b0be;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.25;
}

.team-chip {
  display: flex;
  align-items: center;
  gap: 10px;
}

.team-chip-name {
  font-size: 16px;
  font-weight: 500;
  line-height: 1.25;
  color: #222;
}

.picker-divider {
  height: 1px;
  background: #e6e9ed;
  margin: 0 24px;
}

.swap-btn {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 32px;
  height: 32px;
  border: 1px solid #dbe1ea;
  border-radius: 16px;
  background: #f6f8fc;
  color: var(--primary);
  font-size: 16px;
  cursor: pointer;
}

.team-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #dce3f0;
  flex-shrink: 0;
}

.team-logo {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  object-fit: contain;
  flex-shrink: 0;
}

.calculate-btn {
  width: 100%;
  border: none;
  border-radius: 32px;
  height: 64px;
  background: var(--primary);
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
}

.calculate-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.calculate-error {
  margin: 12px 0 0;
  padding: 12px 16px;
  border-radius: 16px;
  background: rgba(255, 59, 48, 0.12);
  color: #ff3b30;
  font-size: 14px;
  line-height: 1.4;
}

.result-sections {
  margin-top: 12px;
}

.result-card {
  background: var(--card);
  border-radius: 24px;
  padding: 16px 24px;
  margin-bottom: 12px;
}

.result-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.2;
  margin-bottom: 14px;
  color: #111827;
}

.result-table-head,
.result-row {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  column-gap: 12px;
  align-items: center;
}

.result-table-head {
  color: #aab2bd;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 6px;
}

.result-row {
  min-height: 52px;
  border-bottom: 1px solid #e6e9ed;
  font-size: 16px;
  font-weight: 500;
  color: #222;
}

.result-row:last-child {
  border-bottom: none;
}

.result-event {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.event-code {
  color: #222;
}

.event-sub {
  color: #aab2bd;
}

/* Bottom sheet */
.picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.45);
}

.picker-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 201;
  max-height: min(88vh, 640px);
  background: var(--card);
  border-radius: 24px 24px 0 0;
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom, 12px);
}

.picker-sheet-handle {
  width: 36px;
  height: 4px;
  border-radius: 2px;
  background: #dbe1ea;
  margin: 8px auto 4px;
  flex-shrink: 0;
}

.picker-sheet-header {
  display: grid;
  grid-template-columns: 40px 1fr 40px;
  align-items: center;
  padding: 4px 8px 8px;
  border-bottom: 1px solid #e6e9ed;
  flex-shrink: 0;
}

.picker-sheet-back,
.picker-sheet-close {
  border: none;
  background: transparent;
  font-size: 28px;
  line-height: 1;
  color: #222;
  cursor: pointer;
  padding: 4px;
  border-radius: 8px;
}

.picker-sheet-back:active,
.picker-sheet-close:active {
  opacity: 0.6;
}

.picker-sheet-back-spacer {
  width: 40px;
}

.picker-sheet-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  color: #111827;
  line-height: 1.25;
}

.picker-search-wrap {
  padding: 10px 16px 0;
  flex-shrink: 0;
}

.picker-search-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #e6e9ed;
  border-radius: 14px;
  padding: 12px 14px;
  font-size: 16px;
  font-weight: 500;
  color: #222;
  background: #f6f8fc;
}

.picker-search-input::placeholder {
  color: #a8b0be;
}

.picker-sheet-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 8px 0 16px;
}

.picker-muted {
  text-align: center;
  color: #aab2bd;
  font-size: 14px;
  padding: 24px 16px;
}

.picker-list {
  list-style: none;
  margin: 0;
  padding: 0 12px;
}

.picker-league-row,
.picker-team-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  margin-bottom: 8px;
  background: #fff;
  border: 1px solid #e6e9ed;
  border-radius: var(--radius, 16px);
  cursor: pointer;
  transition: transform 0.12s;
}

.picker-league-row:active,
.picker-team-row:active {
  transform: scale(0.99);
}

.picker-league-logo {
  width: 40px;
  height: 40px;
  object-fit: contain;
  flex-shrink: 0;
}

.picker-league-fallback {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #e6e9ed;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  color: var(--primary);
  flex-shrink: 0;
}

.picker-league-name {
  flex: 1;
  font-size: 15px;
  font-weight: 500;
  color: #222;
}

.picker-team-name {
  flex: 1;
  font-size: 16px;
  font-weight: 500;
  color: #222;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker-chevron {
  color: #aab2bd;
  font-size: 20px;
  font-weight: 300;
}

.picker-list--teams .picker-team-row {
  border-color: #eef1f5;
}

.team-option-match {
  font-weight: 700;
  color: var(--primary);
}
</style>
