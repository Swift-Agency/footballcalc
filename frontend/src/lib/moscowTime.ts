export function parseUtcIso(iso: string): Date {
  const normalized = iso.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`
  return new Date(normalized)
}

export function formatMoscowDateTime(iso: string): string {
  try {
    const formatted = parseUtcIso(iso).toLocaleString('ru-RU', {
      day: 'numeric',
      month: 'long',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/Moscow',
    })
    return `${formatted} МСК`
  } catch {
    return iso
  }
}
