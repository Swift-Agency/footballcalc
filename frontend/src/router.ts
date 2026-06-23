import { createRouter, createWebHistory } from 'vue-router'
import CalculatorView from './views/CalculatorView.vue'
import InfoArticleView from './views/InfoArticleView.vue'
import InfoView from './views/InfoView.vue'
import LeagueDetail from './views/LeagueDetail.vue'
import LeagueMatchesView from './views/LeagueMatchesView.vue'
import LeaguesList from './views/LeaguesList.vue'
import MatchDetailView from './views/MatchDetailView.vue'
import ScheduleLeaguesList from './views/ScheduleLeaguesList.vue'
import SubscriptionView from './views/SubscriptionView.vue'
import TeamView from './views/TeamView.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: LeaguesList,
  },
  {
    path: '/leagues',
    name: 'LeaguesList',
    component: LeaguesList,
  },
  {
    path: '/leagues/:id',
    name: 'LeagueDetail',
    component: LeagueDetail,
    props: true,
  },
  {
    path: '/leagues/:id/standings',
    name: 'Standings',
    redirect: '/leagues/:id',
  },
  {
    path: '/leagues/:id/stats',
    name: 'Stats',
    redirect: '/leagues/:id',
  },
  {
    path: '/leagues/:leagueId/team/:teamId',
    name: 'TeamProfile',
    component: TeamView,
    props: true,
  },
  {
    path: '/schedule',
    name: 'ScheduleLeaguesList',
    component: ScheduleLeaguesList,
  },
  {
    path: '/schedule/:id',
    name: 'LeagueMatches',
    component: LeagueMatchesView,
    props: true,
  },
  {
    path: '/schedule/:leagueId/match/:matchId',
    name: 'MatchDetail',
    component: MatchDetailView,
    props: true,
  },
  {
    path: '/calculator',
    name: 'Calculator',
    component: CalculatorView,
  },
  {
    path: '/info',
    name: 'Info',
    component: InfoView,
  },
  {
    path: '/info/subscription',
    name: 'Subscription',
    component: SubscriptionView,
  },
  {
    path: '/info/:slug',
    name: 'InfoArticle',
    component: InfoArticleView,
    props: true,
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
