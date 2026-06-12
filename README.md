# Sourcing Lab

Track the top reels across recruiting, sourcing & career creators. See what's working in the tech-recruiting content niche — outlier scores, spoken-hook transcripts, and 3-second autoplay hook clips — then adapt the winning patterns to your own content. **No AI API key needed** — Apify handles all the AI on their backend.

![Pipeline](https://img.shields.io/badge/pipeline-Admin_UI_→_Apify_→_GitHub_Actions_→_GitHub_Pages-orange)
![Cost](https://img.shields.io/badge/cost-~$2--15_per_month-green)
![No AI key](https://img.shields.io/badge/AI_key_required-no-brightgreen)

## What it does

Every refresh interval (you pick the frequency), a GitHub Action runs and:

1. **Apify scrapes** the last 28 days of reels for your tracked creator list
2. **Pulls spoken transcripts** for any new reels (only pays for new ones — saves ~75% vs naive setup)
3. **ffmpeg extracts** the first 3 seconds of each new reel as a muted autoplay clip
4. **Regenerates** a static HTML dashboard with outlier scores, sortable table, filter-by-creator chips, click-row-to-play hook clip
5. **Pushes** the changes back to the repo → **GitHub Pages auto-redeploys**

## Starter creator list (pre-loaded)

`config.json` ships with recruiting / sourcing / career creators — prune and extend via the admin UI:

| Handle | Who |
|---|---|
| `@advicewitherin` | Erin McGoff — career & life advice (~2M followers) |
| `@workhap` | Sho Dewan — ex-recruiter, career coach (~1M) |
| `@wonsulting` | Wonsulting — job search & careers |
| `@farahsharghi` | Farah Sharghi — career coach, ex-Google recruiter |
| `@bylillianzhang` | Lillian Zhang — early-career content |
| `@hrbestiespod` | HR Besties — HR podcast |
| `@recruitingwithalex` | Recruiting with Alex |

Follower counts in `config.json` are approximate seeds; real numbers come from the first scrape.

## What you need

| Thing | Why | Cost |
|---|---|---|
| **Apify account** | Does the scraping + transcripts | Free $5/mo credit; ~$10–15/mo for 15 creators weekly |
| **GitHub account** | Hosts the code + the dashboard + runs the cron | Free |
| **Python 3.10+** | To run the local admin UI | Free |
| **ffmpeg** | For the 3-sec hook clips | Free |

**You do NOT need:** an OpenAI key, Claude key, a Vercel account, or any other AI subscription. Apify handles all transcription internally; GitHub Pages hosts the dashboard.

## Setup (one time, ~10 minutes)

### 1. Get the code

```bash
git clone https://github.com/Danamove/sourcing-lab.git
cd sourcing-lab
```

### 2. Install ffmpeg

Windows: `winget install ffmpeg` · macOS: `brew install ffmpeg`

### 3. Launch the admin

```bash
python serve.py
```

Your browser opens at `http://localhost:4747/admin`. From there:

- **Paste your Apify token** ([get one free](https://console.apify.com/settings/api))
- **Review the pre-loaded creator list** — remove any, search and add more (recruiters, sourcers, career coaches, HR creators)
- **Pick a schedule** — daily, every 3 days, weekly Sunday, weekly Monday, monthly, or manual-only (times are ~7am Israel)
- **Click "Run refresh now"** to generate the dashboard for the first time
- **Click "Open dashboard ↗"** when it's done

### 4. Push to GitHub + add the secret

```bash
git add config.json .github/workflows/refresh.yml index.html data/ thumbs/ clips/
git commit -m "My setup"
git push

# Make APIFY_TOKEN available to GitHub Actions:
gh secret set APIFY_TOKEN < .env
# (or via UI: repo → Settings → Secrets → Actions → New repository secret)
```

### 5. Enable GitHub Pages

Repo → **Settings → Pages → Deploy from a branch → `main` / `(root)`** — or:

```bash
gh api -X POST repos/OWNER/REPO/pages -f "source[branch]=main" -f "source[path]=/"
```

Your dashboard lives at `https://OWNER.github.io/sourcing-lab/` and redeploys automatically on every push, including the scheduled refresh from GitHub Actions.

> The repo includes a `.nojekyll` file — don't delete it. Without it GitHub Pages runs Jekyll, which silently drops the `thumbs/_profile_*.jpg` files (underscore prefix) and profile pictures vanish.

### 6. Done

The cron you picked in the admin UI fires automatically. You can also trigger manually any time: repo → Actions → Weekly refresh → Run workflow.

## How the cost stays low

The pipeline uses a **two-pass** approach:
- **Pass 1** (cheap, no transcripts): refreshes plays/likes/comments stats for all reels in your 28-day window
- **Pass 2** (transcripts, expensive add-on): only for reels you haven't transcribed yet

That keeps transcript spend roughly flat at "new reels per interval × seconds × $0.041/min" rather than re-paying for the whole archive every refresh.

## Managing your creator list

Run `python serve.py` anytime. The admin remembers everything — search and add new ones, remove old ones, change the schedule. Then `git add config.json && git commit && git push` to propagate the changes to GitHub Actions.

If you prefer the terminal, `python configure.py` also works.

## Architecture

```
┌─────────────────────┐   you click "Run"  ┌──────────────────┐
│   localhost admin   │ ──────────────────▶│   Apify scrape   │
│  (python serve.py)  │◀──── reels + ─────│  + transcripts   │
└──────────┬──────────┘    profile data    └──────────────────┘
           │
           │ refresh.py (download new thumbs + clips, run build.py)
           ▼
┌─────────────────────┐    git push        ┌──────────────────┐
│ index.html + data + │ ──────────────────▶│  GitHub Pages    │
│ thumbs/ + clips/    │                    │  (auto-deploy)   │
└─────────────────────┘                    └──────────────────┘
           ▲                                          │
           │                                          ▼
┌─────────────────────┐                    ┌──────────────────┐
│   GitHub Actions    │                    │  Your dashboard  │
│ (your cron, weekly  │                    │  *.github.io     │
│ or whatever you pick)│                   └──────────────────┘
└─────────────────────┘
```

## Files

| File | What it is |
|---|---|
| **`serve.py`** | Local admin server — run this to get the UI |
| **`admin.html`** | The admin UI (single page, no framework, served by serve.py) |
| `configure.py` | CLI alternative to the web admin (same job) |
| `refresh.py` | The pipeline orchestrator |
| `build.py` | Renders `index.html` from scraped data |
| `extract_clips.py` | ffmpeg helper for the 3-sec hook clips |
| `config.json` | Your creator list (committed; managed by the admin) |
| `.env` | Your Apify token (gitignored) |
| `.github/workflows/refresh.yml` | The cron job — edited by the admin's schedule picker |
| `.nojekyll` | Tells GitHub Pages to serve files as-is (required for `_profile_*` thumbs) |
| `tests/smoke_test.py` | Offline smoke tests — `python tests/smoke_test.py` |
| `data/`, `thumbs/`, `clips/` | Generated content (committed so Pages can serve it) |
| `index.html` | The dashboard (welcome page until first refresh runs) |

## Troubleshooting

**A scheduled run failed.** Check repo → Actions → click the failed run → look at "Run refresh pipeline" step. Most common cause:
- `APIFY_TOKEN` not set as a secret → fix via `gh secret set APIFY_TOKEN < .env`
- A handle in your config went private mid-week → remove via admin

**Apify returned 502.** Transient. `refresh.py` retries with exponential backoff automatically. If it still fails, trigger the workflow again.

**The dashboard shows old data.** Check that GitHub Actions actually committed + pushed (look at the latest commit on the repo). If yes, the `pages-build-deployment` workflow should redeploy within a minute or two.

**Profile pictures missing on the live site.** Make sure `.nojekyll` exists at the repo root (see step 5).

**My profile pictures aren't loading on the admin search results.** Instagram CDN sometimes blocks hotlinked images. The dashboard fixes this by downloading them locally on each refresh; the admin search shows them live so they occasionally 403. Click "Add" anyway — the lookup-and-store happens server-side.

## Credits

Adapted from [outlier-lab](https://github.com/ItsssssJack/outlier-lab) for the tech-recruiting & sourcing niche.

## License

MIT — do what you want with this. Credit appreciated but not required.
