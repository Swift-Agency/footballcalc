import type { League } from './api'

interface LeagueLogoConfig {
  header?: string
  small?: string
}

/** Vite `base` — required for subpath deploys (same host as mini app). */
function publicAsset(path: string): string {
  const base = import.meta.env.BASE_URL
  const root = base.endsWith('/') ? base : `${base}/`
  const p = path.startsWith('/') ? path.slice(1) : path
  return `${root}${p}`
}

function normalizeSstatsId(v: unknown): number | null {
  if (v == null) return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

/**
 * SStats league ids (from api.sstats.net /Leagues) — stable across DB reseeds.
 * Do not key by internal DB `league.id` (auto-increment order differs from competition order).
 */
const LOGOS_BY_SSTATS_ID: Record<number, LeagueLogoConfig> = {
  1: {
    header: publicAsset('logos/world_cup_large.png'),
    small: publicAsset('logos/world_cup_small.png'),
  },
  39: {
    header: publicAsset('logos/epl_large.svg'),
    small: publicAsset('logos/epl_small.svg'),
  },
  140: {
    header: publicAsset('logos/laliga_large.svg'),
    small: publicAsset('logos/laliga_small.svg'),
  },
  135: {
    header: publicAsset('logos/seriea_large.svg'),
    small: publicAsset('logos/seriea_small.svg'),
  },
  78: {
    header: publicAsset('logos/bundesliga_large.svg'),
    small: publicAsset('logos/bundesliga_small.svg'),
  },
  61: {
    header: publicAsset('logos/ligue1_large.svg'),
    small: publicAsset('logos/ligue1_small.svg'),
  },
  235: {
    header: publicAsset('logos/rpl_large.svg'),
    small: publicAsset('logos/rpl_small.svg'),
  },
  2: {
    header: publicAsset('logos/ucl_large.svg'),
    small: publicAsset('logos/ucl_small.svg'),
  },
  3: {
    header: publicAsset('logos/uel_large.svg'),
    small: publicAsset('logos/uel_small.svg'),
  },
  848: {
    header: publicAsset('logos/uecl_large.svg'),
    small: publicAsset('logos/uecl_small.svg'),
  },
}

/** If API omits sstats_id, still map known leagues by key or English name. */
function logoConfigFallback(league: League): LeagueLogoConfig | null {
  if (league.key === 'world_cup') {
    return LOGOS_BY_SSTATS_ID[1] ?? null
  }
  const en = (league.name_en || '').toLowerCase()
  if (en.includes('serie a') || en.includes('serie-a')) {
    return LOGOS_BY_SSTATS_ID[135] ?? null
  }
  if (en.includes('world cup')) {
    return LOGOS_BY_SSTATS_ID[1] ?? null
  }
  return null
}

export function getLeagueHeaderLogo(league: League | null): string | null {
  if (!league) return null
  const sid = normalizeSstatsId(league.sstats_id)
  const cfg =
    (sid != null ? LOGOS_BY_SSTATS_ID[sid] : undefined) ?? logoConfigFallback(league)
  if (cfg?.header) return cfg.header
  return league.logo_url
}

export function getLeagueListLogo(league: League): string | null {
  const sid = normalizeSstatsId(league.sstats_id)
  const cfg =
    (sid != null ? LOGOS_BY_SSTATS_ID[sid] : undefined) ?? logoConfigFallback(league)
  if (cfg?.small) return cfg.small
  return league.logo_small_url || league.logo_url || null
}
