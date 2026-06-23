<template>
  <div class="page">
    <LeagueHeader
      v-if="league"
      :key="league.id"
      :name="league.name"
      :logo-url="getLeagueHeaderLogo(league)"
      :subtitle="formatSeasonSubtitle(league.season)"
    />
    <p v-else-if="loading" class="loading">Загрузка...</p>
    <p v-else class="loading">Лига не найдена</p>

    <template v-if="league">
      <div class="date-filter">
        <button
          v-for="opt in dateOptions"
          :key="opt.days"
          :class="{ active: selectedDays === opt.days }"
          @click="selectedDays = opt.days"
        >
          {{ opt.label }}
        </button>
      </div>

      <div class="matches-content">
        <div
          v-for="group in matchesByDate"
          :key="group.date"
          class="date-wrapper"
        >
          <template v-for="(match, idx) in group.matches" :key="match.id">
            <div class="match-block" @click="goToMatch(match)">
              <div class="match-time">{{ formatDate(group.date) }} {{ match.time }}</div>
              <div class="match-teams">
                <div class="team-row">
                  <img
                    v-if="match.home_team.logo_url"
                    :src="match.home_team.logo_url"
                    :alt="match.home_team.name"
                    class="team-logo"
                  />
                  <div v-else class="team-logo-placeholder" />
                  <span class="team-name">{{ match.home_team.name }}</span>
                </div>
                <div class="team-row">
                  <img
                    v-if="match.away_team.logo_url"
                    :src="match.away_team.logo_url"
                    :alt="match.away_team.name"
                    class="team-logo"
                  />
                  <div v-else class="team-logo-placeholder" />
                  <span class="team-name">{{ match.away_team.name }}</span>
                </div>
              </div>
            </div>
            <div v-if="idx < group.matches.length - 1" class="match-separator" />
          </template>
        </div>

        <div v-if="!loadingMatches && matchesByDate.length === 0" class="empty-state">
          Нет предстоящих матчей
        </div>
      </div>
    </template>

    <p v-if="loadingMatches && league" class="loading">Загрузка матчей...</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getLeagues, getMatches, type League, type Match } from '../api'
import { getLeagueHeaderLogo } from '../leagueLogos'
import LeagueHeader from '../components/LeagueHeader.vue'

const props = defineProps<{ id: string }>()
const router = useRouter()

const league = ref<League | null>(null)
const loading = ref(true)
const matches = ref<Match[]>([])
const loadingMatches = ref(false)
const selectedDays = ref(3)

function formatSeasonSubtitle(season?: number | null): string | undefined {
  if (!season) return undefined
  return `Сезон ${season}/${season + 1}`
}

const dateOptions = [
  { days: 1, label: 'Сегодня' },
  { days: 3, label: '3 дня' },
  { days: 5, label: '5 дней' },
  { days: 7, label: '7 дней' },
]

const matchesByDate = computed(() => {
  const byDate = new Map<string, Match[]>()
  for (const m of matches.value) {
    const list = byDate.get(m.date) ?? []
    list.push(m)
    byDate.set(m.date, list)
  }
  return Array.from(byDate.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, list]) => ({ date, matches: list }))
})

function goToMatch(match: Match) {
  router.push(`/schedule/${props.id}/match/${match.id}`)
}

function formatDate(isoDate: string): string {
  const [y, mo, d] = isoDate.split('-')
  return `${d}.${mo}.${y}`
}

async function loadMatches() {
  if (!props.id) return
  loadingMatches.value = true
  try {
    matches.value = await getMatches(Number(props.id), selectedDays.value)
  } catch (err) {
    console.error('[LeagueMatchesView] failed to load matches:', err)
    matches.value = []
  } finally {
    loadingMatches.value = false
  }
}

watch([() => props.id, selectedDays], () => loadMatches())

onMounted(async () => {
  console.info('[LeagueMatchesView] mounted id=%s', props.id)
  try {
    const all = await getLeagues()
    league.value = all.find((l) => l.id === Number(props.id)) ?? null
  } catch (err) {
    console.error('[LeagueMatchesView] error loading leagues:', err)
  } finally {
    loading.value = false
  }
  await loadMatches()
})
</script>

<style scoped>
.date-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 12px 10px;
}

.date-filter button {
  display: flex;
  flex: 1;
  min-width: 0;
  padding: 10px 10px 12px;
  justify-content: center;
  align-items: center;
  gap: 10px;
  border-radius: 1024px;
  background: #FFF;
  border: none;
  color: #222;
  font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 16px;
  font-weight: 500;
  line-height: 22px;
  cursor: pointer;
  transition: all 0.2s;
}

.date-filter button.active {
  border-radius: 1024px;
  background: #2C3EC4;
  box-shadow: 0 4px 16px 0 rgba(44, 62, 196, 0.24);
  color: #FFF;
}

.matches-content {
  padding: 0 12px 12px;
}

.date-wrapper {
  background: var(--card);
  border-radius: var(--radius);
  margin-bottom: 12px;
  padding: 12px 16px 16px;
  overflow: hidden;
}

.match-block {
  padding: 4px 0;
  cursor: pointer;
  transition: opacity 0.15s;
}

.match-block:active {
  opacity: 0.7;
}

.match-time {
  color: #AAB2BD;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
  margin-bottom: 6px;
}

.match-teams {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.team-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.team-logo,
.team-logo-placeholder {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  flex-shrink: 0;
}

.team-logo {
  object-fit: contain;
}

.team-logo-placeholder {
  background: #E6E9ED;
}

.team-name {
  font-size: 14px;
  font-weight: 500;
  color: #222;
  line-height: 20px;
}

.match-separator {
  height: 1px;
  background: #E6E9ED;
  margin: 8px 0;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
