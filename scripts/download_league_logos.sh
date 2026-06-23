#!/bin/bash
# Download league logos from Wikimedia Commons (public domain / free use).
# Saves to frontend/public/logos/
# Usage: run from repo root

set -e
LOGO_DIR="frontend/public/logos"
mkdir -p "$LOGO_DIR"
cd "$LOGO_DIR"

USER_AGENT="FootballCalculator/1.0 (educational project)"

download() {
  local url="$1"
  local out="$2"
  echo "Downloading $out ..."
  curl -sL -A "$USER_AGENT" -o "$out" "$url" && echo "  OK" || echo "  FAILED"
}

# EPL: keep existing epl.png (user provided). Optional: Commons big version as epl_big.png
# download "https://upload.wikimedia.org/wikipedia/commons/7/79/UK_Premier_League_logo.png" "epl_big.png"

# UEFA Champions League - small (icon) and big (with text)
download "https://upload.wikimedia.org/wikipedia/commons/f/f3/Logo_UEFA_Champions_League.png" "ucl_small.png"
download "https://upload.wikimedia.org/wikipedia/commons/e/e8/Logo_uefa_2012.png" "ucl.png"

# UEFA Europa League - SVG rendered to PNG
download "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/UEFA_Europa_League_logo_%282024_version%29.svg/960px-UEFA_Europa_League_logo_%282024_version%29.svg.png" "uel.png"
download "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/UEFA_Europa_League_logo_%282024_version%29.svg/250px-UEFA_Europa_League_logo_%282024_version%29.svg.png" "uel_small.png"

# UEFA Conference League
download "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/UEFA_Conference_League_full_logo_%282024_version%29.svg/960px-UEFA_Conference_League_full_logo_%282024_version%29.svg.png" "uecl.png"
download "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/UEFA_Conference_League_full_logo_%282024_version%29.svg/250px-UEFA_Conference_League_full_logo_%282024_version%29.svg.png" "uecl_small.png"

# La Liga
download "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/LaLiga_logo_2023.svg/960px-LaLiga_logo_2023.svg.png" "laliga.png"
download "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/LaLiga_logo_2023.svg/250px-LaLiga_logo_2023.svg.png" "laliga_small.png"

# Serie A
download "https://upload.wikimedia.org/wikipedia/commons/c/c2/Serie_A.png" "seriea.png"
download "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Serie_A.png/250px-Serie_A.png" "seriea_small.png"

# Bundesliga
download "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Bundesliga_logo.svg/960px-Bundesliga_logo.svg.png" "bundesliga.png"
download "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Bundesliga_logo.svg/330px-Bundesliga_logo.svg.png" "bundesliga_small.png"

# Ligue 1
download "https://upload.wikimedia.org/wikipedia/commons/f/fb/Ligue1_logo.png" "ligue1.png"
cp -f ligue1.png ligue1_small.png 2>/dev/null || true

echo "RPL: add rpl.png manually if needed."
echo "Done."
