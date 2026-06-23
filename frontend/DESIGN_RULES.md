# Football Calculator — Design Rules

Design principles and specifications for consistent UI development. Use this document when adding or modifying components.

---

## 1. Layout & Wrappers

### App shell
- **Max width**: 480px, centered (`margin: 0 auto`)
- **Page container** (`.page`): flex: 1, bottom padding for nav + safe area
- **Bottom nav height**: 96px (`--bottom-nav-height`)

### Card wrapper (`.card`)
- Background: `var(--card)` (white)
- Border radius: `var(--radius)` (12px)
- Margin: `0 12px 12px`
- Overflow: hidden

### Table wrapper (`.sortable-table-wrapper`)
- **Horizontal padding**: 16px left and right (creates gap for row lines from borders)
- Padding bottom: 4px
- No fixed width — lines have 16px gap from left/right borders

---

## 2. Typography

### Font stack
```css
font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
```

### Body
- Background: `var(--bg)`
- Color: `var(--text)`
- Antialiased, no overscroll

### Section titles (table pages)

**Tournament table page** (StandingsView):
- Color: `#000`
- Font size: 18px
- Font weight: 600
- Line height: 22px
- Padding: `24px 0 6px 23px` (24px above, 23px from left)

**Statistics page** (StatsView — Сводка, Смоллмаркет, Expected Goals):
- Color: `#000`
- Font size: 24px
- Font weight: 600
- Line height: 22px
- Padding: `22px 0 15px 24px` (22px above, 24px from left, 15px to "Команда" header)

---

## 3. Tables (SortableTable)

### Wrapper
- Padding: `0 16px 4px` — row lines have 16px gap from left/right
- No gray background on sortable column headers

### Column headers (th)
- Color: `#AAB2BD`
- Font size: 12px
- Font weight: 500
- First column padding-left: 4px (content 20px from wrapper left when combined with 16px wrapper padding)

### Cells (td)
- Color: `#222`
- Font size: 12px
- Font weight: 500
- Row height: 40px
- Border bottom: `1px solid #E6E9ED`
- First column padding-left: 4px

### Team column (first column)
- Sticky left
- Text left-aligned
- Team name: 16px, weight 500, line-height 22px
- Gap between position badge and logo: 9px (Standings)
- Gap between logo and name: 4px (Stats)

### Position badge (Standings)
- 20px from left wrapper border
- 9px gap to team logo
- 16×16px circle, zone colors (CL, EL, relegation)

---

## 4. Switch / Filter Buttons

### Venue filter (Все матчи / Дома / На выезде)
- **Container**: `inline-flex`, gap 11px, padding `12px 16px 12px 25px` (25px from left screen edge)
- **Unselected**:
  - `border-radius: 1024px`
  - `background: #FFF`
  - `color: #222`
  - Font: 16px, weight 500, line-height 22px
  - Padding: `10px 16px 12px 16px`
- **Selected**:
  - `border-radius: 1024px`
  - `background: #2C3EC4`
  - `box-shadow: 0 4px 16px 0 rgba(44, 62, 196, 0.24)`
  - `color: #FFF`

### Metric tabs (Stats — ЖК, Угловые, etc.)
- Display: flex, gap 4px
- Padding: 8px 12px
- Unselected: border, `var(--card)` bg, `var(--text-secondary)` color, 12px font
- Selected: `var(--primary)` bg, white text

---

## 5. Page Headers

### Gradient header (`.gradient-header`)
- Height: 144px
- Background: `linear-gradient(160deg, var(--primary) 0%, var(--primary-light) 100%)`
- Border radius: `0 0 24px 24px`
- Centered content, white text


### Leagues list header (`.leagues-page-header`)
- Same gradient and height as `.gradient-header`
- H1: 22px, weight 700

---

## 6. Bottom Navigation

### Root state (tabs)
- Background: `var(--primary)`
- Border radius: 20px 20px 0 0
- Tab icons: inactive `#959EE1`, active white

### Back state
- Background: `#2C3EC4`
- Border radius: 24px 24px 0 0
- Box shadow: `0 -8px 32px -4px rgba(44, 62, 196, 0.16)`
- Back button text: 16px, weight 500, line-height 22px, white

---

## 7. Color Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--primary` | #3346D8 | Primary actions, headers |
| `--primary-light` | #2C3EC4 | Gradient, selected states |
| `--bg` | #F3F4F6 | Page background |
| `--card` | #FFFFFF | Cards, table background |
| `--text` | #1F2937 | Body text |
| `--text-secondary` | #6B7280 | Muted text |
| `--border` | #E5E7EB | Borders |
| `--success` | #10B981 | Positive values |
| `--danger` | #EF4444 | Negative values |
| `--radius` | 12px | Card corners |
| `--radius-sm` | 8px | Small elements |

---

## 8. League Icons (List)

- Container: 40×40px, `border-radius: 1024px`, `border: 1px solid #E6E9ED`
- Padding: 10px, flex center
- Logo img: 40×40px, object-fit contain
- SVG fallback: 20×20px inside container

---

## 9. Principles for Next Development

1. **Use CSS variables** — Prefer `var(--primary)`, `var(--card)` over hardcoded colors for consistency.
2. **Respect 16px table padding** — Row lines must have 16px gap from wrapper edges; do not remove `.sortable-table-wrapper` padding.
3. **Section title spacing** — Tournament: 24px above, 23px left. Stats: 22px above, 24px left, 15px to table header.
4. **Switch buttons** — Use `border-radius: 1024px` for pill shape; selected state: #2C3EC4 + box-shadow.
5. **Team cells** — First column: 20px from left (4px padding + 16px wrapper). Gap logo↔name: 4px (Stats) or 9px (Standings with pos-badge).
6. **Font** — Always "SF Pro Display" with fallbacks.
7. **Mobile-first** — Max-width 480px; consider safe-area-inset for bottom nav.
8. **No Telegram theme sync** — App stays bright; do not re-enable `applyTelegramTheme` for dark mode.
