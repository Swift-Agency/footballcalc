import type { Router, RouteLocationNormalizedLoaded } from 'vue-router'

const ROOT_PATHS = new Set(['/', '/leagues', '/schedule', '/calculator', '/info'])

/** Parent route when browser history is empty or back would leave the app. */
export function getFallbackPath(path: string): string {
  if (path.startsWith('/info/subscription')) return '/info'
  if (path.startsWith('/info/')) return '/info'
  if (path.startsWith('/schedule/')) return '/schedule'
  if (path.startsWith('/leagues/')) return '/leagues'
  if (ROOT_PATHS.has(path)) return '/leagues'
  return '/leagues'
}

export function isRootPath(path: string): boolean {
  return ROOT_PATHS.has(path)
}

const ROOT_TAB_PATHS = ['/schedule', '/leagues', '/calculator', '/info'] as const

/** Switch bottom tab without polluting history (Telegram WebView-safe). */
export function navigateRootTab(router: Router, route: RouteLocationNormalizedLoaded, path: string): void {
  if (!ROOT_TAB_PATHS.includes(path as (typeof ROOT_TAB_PATHS)[number])) return
  if (route.path === path) return
  router.replace(path)
}

let backLock = false

/** Single back navigation — safe for Telegram WebView (no double router.back()). */
export function navigateBack(router: Router, route: RouteLocationNormalizedLoaded): void {
  if (backLock) return
  backLock = true
  window.setTimeout(() => {
    backLock = false
  }, 400)

  const fallback = getFallbackPath(route.path)
  const historyIdx = window.history.state?.idx
  if (typeof historyIdx === 'number' && historyIdx > 0) {
    router.back()
    return
  }
  if (route.path !== fallback) {
    router.push(fallback)
  }
}
