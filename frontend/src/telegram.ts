declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp
    }
  }
}

interface ThemeParams {
  bg_color?: string
  text_color?: string
  hint_color?: string
  link_color?: string
  button_color?: string
  button_text_color?: string
  secondary_bg_color?: string
  header_bg_color?: string
  section_bg_color?: string
  accent_text_color?: string
  section_header_text_color?: string
  subtitle_text_color?: string
  destructive_text_color?: string
}

interface SafeAreaInset {
  top?: number
  bottom?: number
  left?: number
  right?: number
}

interface TelegramWebApp {
  ready: () => void
  expand: () => void
  close: () => void
  colorScheme: 'light' | 'dark'
  themeParams: ThemeParams
  headerColor: string
  backgroundColor: string
  initData: string
  initDataUnsafe: Record<string, any>
  safeAreaInset?: SafeAreaInset
  contentSafeAreaInset?: SafeAreaInset
  BackButton: {
    isVisible: boolean
    show: () => void
    hide: () => void
    onClick: (cb: () => void) => void
    offClick: (cb: () => void) => void
  }
  MainButton: {
    text: string
    isVisible: boolean
    show: () => void
    hide: () => void
    onClick: (cb: () => void) => void
    offClick: (cb: () => void) => void
    setParams: (params: { text?: string; color?: string; text_color?: string; is_active?: boolean }) => void
  }
  onEvent: (event: string, cb: () => void) => void
  setHeaderColor: (color: string) => void
  setBackgroundColor: (color: string) => void
}

export function getTelegram(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null
}

export function isTelegramEnv(): boolean {
  return !!window.Telegram?.WebApp?.initData
}

export function initTelegram() {
  const tg = getTelegram()
  if (!tg) return

  tg.ready()
  tg.expand()
  bindSafeAreaCssVars(tg)
}

/** Extra space under Telegram chrome when contentSafeAreaInset is unavailable (iOS header ~48px). */
const TELEGRAM_HEADER_FALLBACK_PX = 48

function resolveSafeTop(tg: TelegramWebApp): number | null {
  const contentTop = tg.contentSafeAreaInset?.top
  const safeTop = tg.safeAreaInset?.top

  if (typeof contentTop === 'number' && contentTop > 0) {
    return contentTop
  }

  if (typeof safeTop === 'number' && safeTop > 0) {
    return safeTop + TELEGRAM_HEADER_FALLBACK_PX
  }

  return null
}

function bindSafeAreaCssVars(tg: TelegramWebApp) {
  const apply = () => {
    const top = resolveSafeTop(tg)
    if (top !== null) {
      document.documentElement.style.setProperty('--app-safe-top', `${top}px`)
    }
  }

  apply()
  tg.onEvent('safe_area_changed', apply)
  tg.onEvent('viewport_changed', apply)
}
