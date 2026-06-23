// In production (served from Railway) the frontend is on the same origin as the
// backend, so we use a relative base and no env var is needed.
// In local dev fall back to localhost so `vite dev` still works.
const _isLocalhost =
  typeof window !== 'undefined' && /localhost|127\.0\.0\.1/.test(window.location.host)

const API_BASE: string =
  import.meta.env.VITE_API_URL ||
  (_isLocalhost
    ? import.meta.env.DEV
      ? '/api'
      : 'http://localhost:8000/api'
    : '/api')

/** True if the app can reach the API. Always true in production (same origin). */
export function isApiConfigured(): boolean {
  return true
}

// ── Simple TTL cache ──────────────────────────────────────────────────────────
interface CacheEntry<T> {
  data: T
  timestamp: number
}

const _cache = new Map<string, CacheEntry<unknown>>()
const DEFAULT_TTL_MS = 5 * 60 * 1000 // 5 minutes

function _fromCache<T>(key: string, ttl = DEFAULT_TTL_MS): T | null {
  const entry = _cache.get(key) as CacheEntry<T> | undefined
  if (!entry) return null
  if (Date.now() - entry.timestamp > ttl) {
    console.debug(`[API] cache expired: ${key}`)
    _cache.delete(key)
    return null
  }
  return entry.data
}

function _toCache<T>(key: string, data: T): void {
  _cache.set(key, { data, timestamp: Date.now() })
}


// ── Core fetch ────────────────────────────────────────────────────────────────
function _getInitData(): string | null {
  try {
    return window.Telegram?.WebApp?.initData || null
  } catch {
    return null
  }
}

/** Error class that carries the parsed backend detail object for 402/401. */
export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `API error ${status}`)
    this.status = status
    this.detail = detail
  }
}

/** Extract nested FastAPI error payload from ApiError.detail. */
export function getApiErrorPayload(err: unknown): Record<string, unknown> | null {
  if (!(err instanceof ApiError)) return null
  const body = err.detail as { detail?: unknown } | Record<string, unknown> | null
  if (!body || typeof body !== 'object') return null
  if ('detail' in body && body.detail && typeof body.detail === 'object') {
    return body.detail as Record<string, unknown>
  }
  return body as Record<string, unknown>
}

/** True if the error is a quota-exhausted 402 from the premium gate. */
export function isQuotaExhausted(err: unknown): err is ApiError {
  const payload = getApiErrorPayload(err)
  return err instanceof ApiError && err.status === 402 && payload?.code === 'quota_exhausted'
}

/** True if the error is a 401 auth-required (no Telegram context). */
export function isAuthRequired(err: unknown): err is ApiError {
  if (!(err instanceof ApiError) || err.status !== 401) return false
  const payload = getApiErrorPayload(err)
  return payload?.code === 'auth_required' || payload === null
}

/** True if the error means legal acceptance is required in Telegram bot. */
export function isLegalAcceptanceRequired(err: unknown): err is ApiError {
  if (!(err instanceof ApiError) || err.status !== 403) return false
  const payload = getApiErrorPayload(err)
  return payload?.code === 'legal_acceptance_required'
}

async function fetchJson<T>(path: string, ttl = DEFAULT_TTL_MS): Promise<T> {
  const cached = _fromCache<T>(path, ttl)
  if (cached !== null) {
    console.debug(`[API] 💾 cache HIT  ${path}`)
    return cached
  }

  const url = `${API_BASE}${path}`
  console.info(`[API] 🌐 fetch  ${url}`)
  const t0 = Date.now()

  const initData = _getInitData()
  const headers: Record<string, string> = {}
  if (initData) headers['X-Telegram-Init-Data'] = initData

  const resp = await fetch(url, { headers })
  const ms = Date.now() - t0

  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    console.error(`[API] ❌ ${resp.status} ${resp.statusText}  ${url}  (${ms}ms)`)
    throw new ApiError(resp.status, detail, `API error ${resp.status}: ${resp.statusText}`)
  }

  const data = (await resp.json()) as T
  const count = Array.isArray(data) ? data.length : 1
  console.info(`[API] ✅ ${resp.status}  ${path}  ${ms}ms  items=${count}`)

  _toCache(path, data)
  return data
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const url = `${API_BASE}${path}`
  const initData = _getInitData()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (initData) headers['X-Telegram-Init-Data'] = initData

  const resp = await fetch(url, {
    method: 'POST',
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  })

  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new ApiError(resp.status, detail, `API error ${resp.status}`)
  }
  return resp.json() as Promise<T>
}

// ── Types ─────────────────────────────────────────────────────────────────────
export interface TeamShort {
  id: number
  name: string
  name_en: string
  logo_url: string | null
  /** Present when returned from API Team model; used e.g. calculator away-team filter. */
  league_id?: number | null
}

export interface League {
  id: number
  key: string | null
  name: string
  name_en: string
  logo_url: string | null
  logo_small_url?: string | null
  country: string | null
  has_groups: boolean
  is_locked: boolean
  season?: number | null
  /** SStats / API league id — stable; use for static logo assets (not internal DB id). */
  sstats_id?: number | null
}

export interface StandingRow {
  position: number
  team: TeamShort
  played: number
  won: number
  drawn: number
  lost: number
  goals_for: number
  goals_against: number
  goal_difference: number
  points: number
}

export interface StandingGroup {
  name: string
  rows: StandingRow[]
}

export interface StandingsResponse {
  rows?: StandingRow[]
  groups?: StandingGroup[]
}

/** Flat list of standing rows (club leagues + World Cup groups). */
export function flattenStandings(response: StandingsResponse): StandingRow[] {
  if (response.groups?.length) {
    return response.groups.flatMap((group) => group.rows)
  }
  return response.rows ?? []
}

export interface TeamProfileSummary {
  team: TeamShort
  matches: number
  srt: number
  srt1: number
  srt2: number
  obz_pct: number
}

export interface TeamSmallmarketMetric {
  metric: string
  label: string
  srt: number
  srt1: number
  srt2: number
}

export interface TeamProfileXg {
  team: TeamShort
  matches: number
  xg: number
  xga: number
  delta_g: number
  delta_ga: number
}

export interface TeamProfileResponse {
  team: TeamShort
  summary: TeamProfileSummary
  smallmarkets: TeamSmallmarketMetric[]
  xg: TeamProfileXg | null
}

export interface AdvancedStatsRow {
  team: TeamShort
  matches: number
  srt: number
  srt1: number
  srt2: number
  obz_pct: number
}

export interface SmallMarketRow {
  team: TeamShort
  matches: number
  srt: number
  srt1: number
  srt2: number
}

export interface XgRow {
  team: TeamShort
  matches: number
  xg: number
  xga: number
  delta_g: number
  delta_ga: number
}

export type VenueType = 'all' | 'home' | 'away'

/** Upcoming match for schedule view. Ready for backend: replace mock with fetchJson. */
export interface Match {
  id: number
  /** ISO date string (YYYY-MM-DD) */
  date: string
  /** Time string HH:mm */
  time: string
  home_team: TeamShort
  away_team: TeamShort
}

/** Team stats row for match detail. */
export interface MatchTeamStats {
  position: number
  team: TeamShort
  srt: number
  srt1: number
  srt2: number
  obz_pct: number
  matches: number
  points: number
}

/** Match detail with teams and stats. */
export interface MatchDetail {
  match: Match
  general_stats: [MatchTeamStats, MatchTeamStats]
  by_position_stats: [MatchTeamStats, MatchTeamStats]
}

export interface CalculatorOddsRow {
  event: string
  subevent?: string
  probability: number
  odds: number
}

export interface CalculatorSection {
  id: string
  title: string
  rows: CalculatorOddsRow[]
}

export interface CalculatorResult {
  home_team: TeamShort
  away_team: TeamShort
  main_outcomes: CalculatorOddsRow[]
  sections: CalculatorSection[]
}
export type SmallMarketMetric =
  | 'yellow_cards'
  | 'corners'
  | 'shots_on_target'
  | 'shots_total'
  | 'fouls'
  | 'offsides'

// ── Premium / Quota / Billing types ──────────────────────────────────────────

export interface UsageQuota {
  is_unlimited: boolean
  weekly_limit: number
  used: number
  remaining: number
  resets_at: string | null
}

export interface BillingConfig {
  price_rub: number
  discount_price_rub: number
  period_days: number
  world_cup_ends_at: string
  weekly_free_quota: number
  referral_discount_percent?: number
  bot_username?: string | null
}

export interface BillingMeResponse {
  is_subscribed: boolean
  is_unlimited: boolean
  plan_type: 'monthly' | 'world_cup' | null
  status: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  quota: UsageQuota | null
  referral_code: string | null
  referral_link: string | null
  has_discount: boolean
  discount_expires_at: string | null
}

export interface CheckoutResponse {
  confirmation_url: string
  payment_id: number
}

export interface PaymentStatus {
  payment_id: number
  status: string
}

export interface ReferralStats {
  referral_code: string | null
  referral_link: string | null
  referred_count: number
  converted_count: number
}

// ── Endpoints ─────────────────────────────────────────────────────────────────
export const getLeagues = () => {
  console.debug('[API] getLeagues')
  return fetchJson<League[]>('/leagues')
}

export const getStandings = (leagueId: number, venue: VenueType = 'all') => {
  const path = `/leagues/${leagueId}/standings?venue=${venue}`
  console.debug('[API] getStandings leagueId=%d venue=%s', leagueId, venue)
  return fetchJson<StandingsResponse>(path)
}

export const getAdvancedStats = (leagueId: number, venue: VenueType = 'all') => {
  const path = `/leagues/${leagueId}/advanced-stats?venue=${venue}`
  console.debug('[API] getAdvancedStats leagueId=%d venue=%s', leagueId, venue)
  return fetchJson<AdvancedStatsRow[]>(path)
}

export const getSmallMarkets = (
  leagueId: number,
  metric: SmallMarketMetric,
  venue: VenueType = 'all',
) => {
  const path = `/leagues/${leagueId}/smallmarkets?metric=${metric}&venue=${venue}`
  console.debug('[API] getSmallMarkets leagueId=%d metric=%s venue=%s', leagueId, metric, venue)
  return fetchJson<SmallMarketRow[]>(path)
}

export const getXgStats = (leagueId: number, venue: VenueType = 'all') => {
  const path = `/leagues/${leagueId}/xg?venue=${venue}`
  console.debug('[API] getXgStats leagueId=%d venue=%s', leagueId, venue)
  return fetchJson<XgRow[]>(path, 0)  // TTL=0: quota consumed on each call; don't use cached data
}

/**
 * Upcoming matches for a league.
 */
export async function getMatches(leagueId: number, days: number = 7): Promise<Match[]> {
  const path = `/leagues/${leagueId}/matches?days=${days}`
  console.debug('[API] getMatches leagueId=%d days=%d', leagueId, days)
  return fetchJson<Match[]>(path, 60 * 1000)
}


/**
 * Match detail with team stats.
 */
export async function getMatchDetail(leagueId: number, matchId: number): Promise<MatchDetail | null> {
  const path = `/leagues/${leagueId}/matches/${matchId}`
  console.debug('[API] getMatchDetail leagueId=%d matchId=%d', leagueId, matchId)
  return fetchJson<MatchDetail>(path, 60 * 1000)
}

/**
 * Team profile (summary + smallmarkets + xG) aggregated in a single request.
 */
export async function getTeamProfile(
  leagueId: number,
  teamId: number,
  venue: VenueType = 'all',
): Promise<TeamProfileResponse> {
  const path = `/leagues/${leagueId}/teams/${teamId}/profile?venue=${venue}`
  return fetchJson<TeamProfileResponse>(path, 2 * 60 * 1000)
}

export interface GlobalSearchResult {
  leagues: { id: number; name: string; name_en: string }[]
  teams: {
    id: number
    name: string
    name_en: string
    league_id: number
    logo_url: string | null
  }[]
  matches: {
    id: number
    league_id: number
    home_team: { id: number; name: string }
    away_team: { id: number; name: string }
    date: string | null
    status: string
  }[]
}

/**
 * Unified search (leagues, teams, matches). Minimum query length 2 on the server.
 */
export async function globalSearch(query: string): Promise<GlobalSearchResult> {
  const q = encodeURIComponent(query.trim())
  const path = `/search?q=${q}`
  return fetchJson<GlobalSearchResult>(path, 30 * 1000)
}

/**
 * Search teams for calculator.
 * Omit leagueId to list/search across all leagues (home team).
 * Pass leagueId (e.g. home team's league) so away team stays in the same league as required by odds API.
 */
export async function searchCalculatorTeams(
  query: string,
  options?: { leagueId?: number },
): Promise<TeamShort[]> {
  const q = encodeURIComponent(query.trim())
  let path = `/calculator/teams?query=${q}`
  if (options?.leagueId != null) path += `&leagueId=${options.leagueId}`
  return fetchJson<TeamShort[]>(path, 30 * 1000)
}

/**
 * Calculator odds result. Throws ApiError on 401/402 (quota exhausted / auth required).
 */
export async function calculateOdds(homeTeamId: number, awayTeamId: number): Promise<CalculatorResult> {
  const path = `/calculator/odds?homeTeamId=${homeTeamId}&awayTeamId=${awayTeamId}`
  return fetchJson<CalculatorResult>(path, 0)  // TTL=0: never cache (quota is consumed on each call)
}

// ── Billing endpoints ─────────────────────────────────────────────────────────

export async function getBillingConfig(): Promise<BillingConfig> {
  return fetchJson<BillingConfig>('/billing/config', 10 * 60 * 1000)
}

export async function getBillingMe(): Promise<BillingMeResponse> {
  return fetchJson<BillingMeResponse>('/billing/me', 0)
}

export interface CheckoutOptions {
  return_url?: string
  plan_type?: 'monthly' | 'world_cup'
}

export async function createCheckout(options?: CheckoutOptions | string): Promise<CheckoutResponse> {
  // Back-compat: allow string (old call sites pass return_url directly)
  const body: Record<string, string> =
    typeof options === 'string'
      ? { return_url: options }
      : { ...(options?.return_url ? { return_url: options.return_url } : {}), plan_type: options?.plan_type ?? 'monthly' }
  return postJson<CheckoutResponse>('/billing/checkout', body)
}

export async function pollPayment(paymentId: number): Promise<PaymentStatus> {
  return fetchJson<PaymentStatus>(`/billing/payments/${paymentId}`, 0)
}

export async function cancelSubscription(): Promise<void> {
  await postJson('/billing/cancel')
}

export async function resumeSubscription(): Promise<void> {
  await postJson('/billing/resume')
}

// ── Referral endpoints ────────────────────────────────────────────────────────

export async function claimReferral(referral_code: string): Promise<{ ok: boolean; has_discount?: boolean; message?: string }> {
  return postJson('/referrals/claim', { referral_code })
}

export async function getReferralStats(): Promise<ReferralStats> {
  return fetchJson<ReferralStats>('/referrals/me', 0)
}

