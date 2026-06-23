# League logos

- **Big logos** (with text): used in league header (`logo_url`). Files: `epl.png`, `ucl.png`, `uel.png`, `uecl.png`, `laliga.png`, `seriea.png`, `bundesliga.png`, `ligue1.png`.
- **Small logos** (icons): used in leagues list (`logo_small_url`). SVG files: `*_small.svg` (e.g. `epl_small.svg`, `ucl_small.svg`). Sourced from project root `new_small_logos`.
- **EPL**: `epl.png` is used for both (user-provided). Optional: run `scripts/download_league_logos.sh` does not overwrite it.
- **RPL**: add `rpl.png` and optionally `rpl_small.png` manually (no free source on Commons). Until then, the list shows a placeholder for RPL.

To refresh logos from Wikimedia Commons (except EPL and RPL):

```bash
./scripts/download_league_logos.sh
```
