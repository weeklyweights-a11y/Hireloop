# HireLoop

**Live US job data from 250+ company career pages — refreshed every ~2 hours — for browsers and AI clients.**

HireLoop is a self-hosted job-data platform. It polls company ATS APIs (Greenhouse, Lever, Ashby, Workday, and custom endpoints), parses each listing into structured fields, stores them in Postgres, builds a Neo4j skill/role graph, and exposes everything through:

| Interface | URL | Who uses it |
|---|---|---|
| **Web UI** | `http://localhost:8000/` | You in a browser — browse, filter, upload resume, ranked matches |
| **MCP** | `http://localhost:8000/mcp` | Cursor, Claude Desktop, ChatGPT, any Streamable-HTTP MCP client |
| **REST** | `http://localhost:8000/jobs/*` | Scripts, integrations, the Web UI itself |

Every job is verified on the company’s own career page. No aggregator scrapers. No ghost listings that vanished months ago. HireLoop hosts **no LLM** — your AI client (or the heuristic matcher) does the reasoning.

> Inspired by the open job-search tooling wave: AI helps you **choose** roles worth your time. HireLoop’s job is the other half — **fresh, structured, source-verified listings** that those agents can query.

---

## What you get

| Feature | Description |
|---|---|
| **Live polling** | ~250 configured sources; full poll about every 2 hours |
| **Structured jobs** | Title, location, remote policy, salary, seniority, skills, visa, apply URL |
| **Web Browse** | Search + filters (location, remote, experience, salary, seniority, visa, **posted date**) |
| **Web Matches** | Upload/paste resume → extract skills → preferences → ranked matches via **MCP `match_jobs`** |
| **Skill graph** | Neo4j expansions (e.g. TensorFlow → Python / Deep Learning) for search & matching |
| **13 MCP tools** | Search, match, gaps, company stack, watches, stats, and more |
| **REST API** | Same data for any HTTP client |
| **Admin** | Toggle sources, trigger poll / graph rebuild (`ADMIN_KEY` optional) |

---

## Requirements

- **Docker Desktop** (or Docker Engine + Compose v2)
- About **3 GB RAM** free (Postgres + Redis + Neo4j + API + worker; Neo4j is the heavy piece)
- Ports free: `8000`, `5432`, `6379`, `7474`, `7687`

---

## Quick start

```bash
git clone https://github.com/weeklyweights-a11y/Hireloop.git
cd Hireloop

# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env

docker compose up --build
```

First boot will:

1. Migrate Postgres  
2. Seed ATS source configs + graph seed data  
3. Run an **initial poll** when the job table is empty (can take several minutes)

Then open:

- Web UI → [http://localhost:8000/](http://localhost:8000/)  
- Health → [http://localhost:8000/health](http://localhost:8000/health)  
- Stats → [http://localhost:8000/stats](http://localhost:8000/stats)  

Stop with `Ctrl+C`, or run detached: `docker compose up --build -d`.

---

## Connect an AI client (MCP)

HireLoop speaks **Streamable HTTP** MCP at `/mcp`.

### Cursor

Settings → MCP → Add server → URL:

```text
http://localhost:8000/mcp
```

Or project `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "hireloop": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Claude Desktop

```json
{
  "mcpServers": {
    "hireloop": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Example prompts

- “Find remote senior backend jobs that mention Python”  
- “Match me to jobs given Python, Flask, and AWS — prefer SF or remote”  
- “What am I missing for a Machine Learning Engineer role?”  
- “What’s Stripe hiring for right now?”  
- “Watch Anthropic and OpenAI for new ML openings”  

---

## Web UI guide

### Browse Jobs

- Full-text search + filters: location (city / Remote / United States), remote policy, experience, salary min, seniority, visa, **Posted** (Any · 24h · 7d · 30d)
- Sort: newest / salary high / salary low  
- Pagination (20 per page)  
- Expand a card for description + skills; **Apply** opens the company link (or **No apply link** if the ATS didn’t provide one)

### My Matches

1. Upload a PDF resume (text extracted in-browser) or paste text  
2. Review / edit extracted skills  
3. Set preferences (role, location, remote, salary, seniority, visa, companies, posted window)  
4. **Find Matches** → browser calls MCP `match_jobs`  
5. Page through **all** ranked matches; on the last page you’ll see a **You’re done** note with time until the next poll  

Resume PDF bytes are not stored on disk; parsing is local/heuristic (no cloud LLM required for the UI path).

---

## MCP tools (13)

| Tool | Purpose |
|---|---|
| `search_jobs` | Filtered search; optional `my_skills` → `quick_match` |
| `get_job_details` | Full JD + apply URL + market context |
| `list_companies` | Companies monitored + active counts |
| `get_company_jobs` | All open roles at one company |
| `get_stats` | Platform totals |
| `get_new_jobs` | Jobs first seen in the last N hours |
| `get_role_insights` | Skills / pay / companies for a role |
| `get_skill_insights` | Roles / pay / companies for a skill |
| `get_company_stack` | Tech stack + hiring mix |
| `match_jobs` | Ranked fit from skills + preferences (supports `offset` paging) |
| `analyze_skills` | Market positioning for a skill set |
| `get_skill_gaps` | Have / close / need for a target role |
| `create_watch` | Client-side watch config (re-poll with `posted_within_hours`) |

Rate limit: **100 requests / hour / IP** on `/mcp`.

---

## How it works

```text
ATS career APIs  ──poll ~2h──►  Parser  ──►  Postgres (jobs)
                                      └──►  Neo4j (skills / roles / companies)
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
               Web UI (REST)            MCP /mcp                  REST clients
```

- **No scrapers of HTML career sites as the primary path** — configured JSON APIs per company where possible  
- Jobs missing from two consecutive polls are closed  
- Matching: SQL pre-filter → score (skills / role / preferences / freshness) → rank; skills expand through the graph when Neo4j is up  

Useful ops endpoints (with stack running):

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | DB status, last/next poll |
| `GET` | `/admin/poll/status` | New / updated / closed counts for last poll |
| `POST` | `/admin/poll` | Trigger a poll now |
| `POST` | `/admin/graph/rebuild` | Rebuild Neo4j relationships |
| `GET` | `/admin/sources` | List / inspect sources |

Set `ADMIN_KEY` in `.env` to require `X-Admin-Key` on `/admin/*`. Empty key = open (local default).

---

## Project layout

```text
Hireloop/
├── docker-compose.yml      # postgres, redis, neo4j, api, worker
├── Dockerfile              # API image
├── Dockerfile.worker       # Celery worker
├── .env.example            # Copy to .env
├── SETUP.txt               # Short run sheet
├── requirements.txt
├── alembic/                # DB migrations
├── scripts/                # seed, poll helpers, taxonomy builders
├── src/
│   ├── main.py             # FastAPI app
│   ├── mcp/                # MCP server + tools
│   ├── routers/            # REST
│   ├── services/           # poll, parse, search, match
│   ├── graph/              # Neo4j
│   ├── static/             # Web UI (vanilla JS)
│   ├── data/               # locations, skills, source JSON
│   └── workers/            # Celery tasks / schedules
└── tests/
```

---

## Configuration

Copy `.env.example` → `.env`. Important variables:

| Variable | Default (dev) | Meaning |
|---|---|---|
| `DATABASE_URL` | async Postgres URL | API DB |
| `REDIS_URL` | `redis://…` | Celery / cache |
| `NEO4J_URI` / `USER` / `PASSWORD` | local bolt | Skill graph |
| `POLL_INTERVAL_HOURS` | `2` | Schedule cadence |
| `ADMIN_KEY` | empty | Lock admin routes |
| `RATE_LIMIT_PER_HOUR` | `100` | MCP IP limit |

Compose overrides many of these for container networking; `.env` matters most for local non-Docker runs.

---

## Development (optional)

```bash
# Infra only
docker compose up postgres redis neo4j -d

python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -r requirements.txt

# migrate + run API (see entrypoint.sh / project scripts for full flow)
```

Tests:

```bash
pytest -q
```

After changing static UI files, rebuild the API image (`docker compose build api && docker compose up -d api`) — static assets are copied into the image, not bind-mounted.

---

## Data freshness & expectations

- Header “Updated X ago” = last successful full poll, not a filter you set  
- **Posted** filters use `first_seen` (when HireLoop first observed the job)  
- Role labels matter: e.g. “AI/ML Engineer” may have far fewer normalized titles than “Machine Learning Engineer” or “Data Scientist”  
- First poll populates tens of thousands of active jobs (depends on sources); later polls add/update/close deltas — see `/admin/poll/status`  

---

## What this is not

- Not a resume tailor / cover-letter generator (see tools like [career-ops](https://github.com/santifer/career-ops) for that loop)  
- Not a hosted SaaS — you run it locally (or on your own cloud)  
- Not an LLM host — matching in the UI is heuristic + graph; chat clients bring their own models  

---

## License

MIT — see [LICENSE](LICENSE).

---

## Troubleshooting

| Symptom | Likely fix |
|---|---|
| UI looks old after a pull | `docker compose build api && docker compose up -d api` + hard refresh |
| Neo4j / match errors | Wait for Neo4j healthy; check `docker compose ps` |
| Empty Browse | Clear filters; “United States” maps to country `US` |
| Few Matches for a role | Try a broader target role or clear it; check Posted filter |
| MCP tools missing in Cursor | Confirm `http://localhost:8000/mcp` and that the API container is up |

Health JSON (`/health`) shows `last_poll`, `next_poll`, and active job counts — start there when debugging.

Contact: bhargavin189@gmail.com
