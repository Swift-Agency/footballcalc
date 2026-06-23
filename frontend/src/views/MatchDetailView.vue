<template>
  <div class="page">
    <header v-if="detail" class="match-detail-header">
      <div class="match-header-center">
        <div class="team-block">
          <img
            v-if="detail.match.home_team.logo_url"
            :src="detail.match.home_team.logo_url"
            :alt="detail.match.home_team.name"
            class="team-logo-header"
          />
          <div v-else class="team-logo-placeholder-header" />
          <span class="team-name-header">{{ detail.match.home_team.name }}</span>
        </div>
        <div class="match-time-block">
          <span class="match-time-main">{{ detail.match.time }}</span>
          <span class="match-date">{{ formatDate(detail.match.date) }}</span>
        </div>
        <div class="team-block">
          <img
            v-if="detail.match.away_team.logo_url"
            :src="detail.match.away_team.logo_url"
            :alt="detail.match.away_team.name"
            class="team-logo-header"
          />
          <div v-else class="team-logo-placeholder-header" />
          <span class="team-name-header">{{ detail.match.away_team.name }}</span>
        </div>
      </div>
    </header>

    <template v-if="detail">
      <div class="stats-cards">
        <div class="card stats-card">
          <div class="section-head">
            <h3 class="card-section-title">Общая статистика</h3>
            <button
              type="button"
              class="info-btn"
              aria-label="Справка по колонкам"
              @click="openInfo('general')"
            >
              <img :src="infoIconSrc" alt="" width="15" height="15" />
            </button>
          </div>
          <div class="match-stats-table-wrapper">
            <table class="match-stats-table">
              <colgroup>
                <col class="col-team" />
                <col class="col-num" />
                <col class="col-num" />
                <col class="col-num" />
                <col class="col-num" />
                <col class="col-num" />
                <col class="col-num" />
              </colgroup>
              <thead>
                <tr>
                  <th>Команда</th>
                  <th>СРТ</th>
                  <th>СРТ1</th>
                  <th>СРТ2</th>
                  <th>ОБЗ%</th>
                  <th>Матчи</th>
                  <th>ОЧК</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in detail.general_stats" :key="row.team.id">
                  <td class="team-cell-td">
                    <div class="team-cell">
                      <span class="pos-num">{{ row.position }}</span>
                      <img
                        v-if="row.team.logo_url"
                        :src="row.team.logo_url"
                        :alt="row.team.name"
                        class="team-logo-sm"
                      />
                      <div v-else class="team-logo-placeholder-sm" />
                      <span class="team-name-cell">{{ row.team.name }}</span>
                    </div>
                  </td>
                  <td>{{ row.srt }}</td>
                  <td>{{ row.srt1 }}</td>
                  <td>{{ row.srt2 }}</td>
                  <td>{{ row.obz_pct }}%</td>
                  <td>{{ row.matches }}</td>
                  <td>{{ row.points }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card stats-card">
          <div class="section-head">
            <h3 class="card-section-title">По амплуа</h3>
            <button
              type="button"
              class="info-btn"
              aria-label="Справка по колонкам"
              @click="openInfo('venue')"
            >
              <img :src="infoIconSrc" alt="" width="15" height="15" />
            </button>
          </div>
          <div class="match-stats-table-wrapper">
            <table class="match-stats-table">
              <colgroup>
                <col class="col-team" />
                <col class="col-num" />
                <col class="col-num" />
                <col class="col-num" />
                <col class="col-num" />
                <col class="col-num" />
                <col class="col-num" />
              </colgroup>
              <thead>
                <tr>
                  <th>Команда</th>
                  <th>СРТ</th>
                  <th>СРТ1</th>
                  <th>СРТ2</th>
                  <th>ОБЗ%</th>
                  <th>Матчи</th>
                  <th>ОЧК</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in detail.by_position_stats" :key="row.team.id">
                  <td class="team-cell-td">
                    <div class="team-cell">
                      <span class="pos-num">{{ row.position }}</span>
                      <img
                        v-if="row.team.logo_url"
                        :src="row.team.logo_url"
                        :alt="row.team.name"
                        class="team-logo-sm"
                      />
                      <div v-else class="team-logo-placeholder-sm" />
                      <span class="team-name-cell">{{ row.team.name }}</span>
                    </div>
                  </td>
                  <td>{{ row.srt }}</td>
                  <td>{{ row.srt1 }}</td>
                  <td>{{ row.srt2 }}</td>
                  <td>{{ row.obz_pct }}%</td>
                  <td>{{ row.matches }}</td>
                  <td>{{ row.points }}</td>
                </tr>
              </tbody>
            </table>
          </div>
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
    <p v-else class="loading">Матч не найден</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getMatchDetail, type MatchDetail } from '../api'
import ColumnInfoModal from '../components/ColumnInfoModal.vue'
import { MATCH_TABLE_INFO_LINES } from '../columnInfoLines'
import infoIconSrc from '../assets/info-icon.svg'

const props = defineProps<{ leagueId: string; matchId: string }>()
const detail = ref<MatchDetail | null>(null)
const loading = ref(true)

const infoOpen = ref(false)
type MatchInfoContext = 'general' | 'venue'
const infoContext = ref<MatchInfoContext>('general')

const infoModalContent = computed(() => ({
  title: infoContext.value === 'general' ? 'Общая статистика' : 'По амплуа',
  lines: MATCH_TABLE_INFO_LINES,
}))

function openInfo(ctx: MatchInfoContext) {
  infoContext.value = ctx
  infoOpen.value = true
}

function formatDate(isoDate: string): string {
  const [y, mo, d] = isoDate.split('-')
  return `${d}.${mo}.${y}`
}

onMounted(async () => {
  console.info('[MatchDetailView] mounted leagueId=%s matchId=%s', props.leagueId, props.matchId)
  try {
    detail.value = await getMatchDetail(Number(props.leagueId), Number(props.matchId))
  } catch (err) {
    console.error('[MatchDetailView] failed to load match:', err)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.match-detail-header {
  background: linear-gradient(160deg, var(--primary) 0%, var(--primary-light) 100%);
  border-radius: 0 0 24px 24px;
  box-sizing: border-box;
  height: calc(177px + var(--app-safe-top) + var(--header-title-offset));
  padding: calc(var(--app-safe-top) + var(--header-title-offset)) 16px 16px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  color: white;
}

.match-header-center {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.team-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.team-logo-header,
.team-logo-placeholder-header {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  flex-shrink: 0;
}

.team-logo-placeholder-header {
  background: rgba(255, 255, 255, 0.3);
}

.team-name-header {
  font-size: 16px;
  font-weight: 500;
  line-height: 1.2;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

.match-time-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.match-time-main {
  font-size: 40px;
  font-weight: 500;
  line-height: 1.2;
}

.match-date {
  font-size: 18px;
  opacity: 0.9;
}

.stats-cards {
  padding-top: 8px;
}

.stats-card {
  margin-bottom: 12px;
  /* Global .card uses overflow:hidden which clips table/flex layout on narrow screens */
  overflow: visible;
}

.stats-card:last-child {
  margin-bottom: 0;
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

.match-stats-table-wrapper {
  padding: 0 12px 14px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.match-stats-table {
  width: 100%;
  min-width: 320px;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
}

.match-stats-table col.col-team {
  width: 40%;
}

.match-stats-table col.col-num {
  width: 10%;
}

.match-stats-table th {
  color: #AAB2BD;
  font-weight: 500;
  padding: 8px 5px;
  text-align: center;
  white-space: nowrap;
  font-size: 11px;
  letter-spacing: 0.01em;
}

.match-stats-table thead tr {
  border-bottom: 1px solid #E6E9ED;
}

.match-stats-table th:first-child {
  text-align: left;
  padding-left: 2px;
  padding-right: 6px;
}

.match-stats-table td {
  color: #222;
  font-weight: 500;
  padding: 6px 5px;
  height: 44px;
  text-align: center;
  border-bottom: none;
  vertical-align: middle;
  white-space: nowrap;
}

.match-stats-table tbody tr:not(:last-child) {
  border-bottom: 1px solid #E6E9ED;
}

.team-cell-td {
  text-align: left;
  padding-left: 2px;
  padding-right: 6px;
  vertical-align: middle;
}

.team-cell {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.pos-num {
  min-width: 14px;
  color: #AAB2BD;
  text-align: center;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 10px;
  font-style: normal;
  font-weight: 500;
  line-height: normal;
}

.team-logo-sm,
.team-logo-placeholder-sm {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  flex-shrink: 0;
}

.team-logo-placeholder-sm {
  background: #E6E9ED;
}

.team-name-cell {
  color: #222;
  text-align: left;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 13px;
  font-style: normal;
  font-weight: 500;
  line-height: 1.25;
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
