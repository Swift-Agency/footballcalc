import type { League } from './api'

/** Matches Figma league list order. */
export const LEAGUE_DISPLAY_ORDER = [
  'world_cup',
  'ucl',
  'uel',
  'uecl',
  'epl',
  'laliga',
  'serie_a',
  'bundesliga',
  'ligue_1',
  'rpl',
] as const

export function sortLeaguesByDisplayOrder<T extends Pick<League, 'key'>>(leagues: T[]): T[] {
  const order = LEAGUE_DISPLAY_ORDER as readonly string[]
  return [...leagues].sort((a, b) => {
    const ai = a.key ? order.indexOf(a.key) : order.length
    const bi = b.key ? order.indexOf(b.key) : order.length
    return (ai === -1 ? order.length : ai) - (bi === -1 ? order.length : bi)
  })
}
