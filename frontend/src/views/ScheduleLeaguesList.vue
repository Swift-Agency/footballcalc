<template>
  <div class="page leagues-page">
    <div class="leagues-page-header">
      <div class="leagues-page-header-inner">
        <h1>Расписание</h1>
      </div>
    </div>

    <WorldCupBanner
      v-if="worldCupLeague"
      :locked="false"
      @click="handleLeagueClick(worldCupLeague)"
    />

    <LeaguesListCard
      :leagues="displayLeagues"
      :loading="loading"
      @select="handleLeagueClick"
    />

    <p v-if="loading" class="loading">Загрузка...</p>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getLeagues, type League } from '../api'
import { sortLeaguesByDisplayOrder } from '../leagueOrder'
import WorldCupBanner from '../components/WorldCupBanner.vue'
import LeaguesListCard from '../components/LeaguesListCard.vue'

const router = useRouter()
const leagues = ref<League[]>([])
const loading = ref(true)

const worldCupLeague = computed(() =>
  leagues.value.find((l) => l.key === 'world_cup') ?? null,
)

const displayLeagues = computed(() => sortLeaguesByDisplayOrder(leagues.value))

function handleLeagueClick(league: League) {
  router.push(`/schedule/${league.id}`)
}

onMounted(async () => {
  try {
    leagues.value = await getLeagues()
  } catch (err) {
    console.error('[ScheduleLeaguesList] failed to load leagues:', err)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.leagues-page {
  padding-bottom: calc(var(--bottom-nav-current-height) + 12px + env(safe-area-inset-bottom));
}
</style>
