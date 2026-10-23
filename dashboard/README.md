# CONUS dashboard (Flask)

Map (D3 + us-atlas states), focus readout and chat pane over live airline traffic. The dashboard
only **reads** Postgres, which the ingest worker fills from OpenSky every 90 s. It never calls an
external API.

- The browser asks for a snapshot every 5 s. The server answers `304 Not Modified` until a new poll
  lands (ETag = poll id).
- Between polls, the browser dead-reckons airborne planes from ground speed and track, so they
  move smoothly, then snaps them to the reported position on the next poll. Extrapolated positions
  are marked "est." in the readout.
- Chat is a deterministic lookup (callsign, airport code, counts) until the LLM agent arrives (P6).

## Run

From the repo root (needs `.env`, see `.env.example`):

    docker compose up -d --build                    # postgres + ingest + dashboard
    INGEST_SOURCE=replay docker compose up -d       # synthetic data, no OpenSky calls
    # then http://localhost:8080

For UI work outside Docker, with Postgres from Compose running:

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    set -a; . ../.env; set +a; .venv/bin/flask --app app run --debug --port 8080

## Layout

    app.py                 Flask routes
    conus/store.py         read-only queries against the ingest DB, unit conversion
    conus/chat.py          deterministic chat stub (until P6)
    conus/airports.py      airport table (replaced by OurAirports in P2)
    templates/index.html   page shell (CSS lives here)
    static/app.js          D3 map, extrapolation, readout, chat client
    static/geo/*.json      us-atlas states + world land TopoJSON
    static/vendor/         d3, topojson-client

## API

| Method | Path                 | Returns |
|--------|----------------------|---------|
| GET    | /api/airports        | `[[IATA, name, lat, lon], ...]` |
| GET    | /api/airlines        | `{icao: name}` (the allowlist) |
| GET    | /api/aircraft        | `{ts, poll_ts, aircraft: [...]}`: aircraft heard from in the last 5 min; `ETag`/`304` |
| GET    | /api/aircraft/<id>   | one aircraft by icao24 or callsign |
| GET    | /api/health          | `{db_ok, last_poll_age_s, last_poll_kept, credits_remaining}` |
| POST   | /api/chat            | body `{"q": str, "selected": {kind, id} \| null}`; returns `{parts, focus}` |

Aircraft fields: `id`/`icao24`, `callsign`, `airline` (ICAO prefix), `status` (`flight`/`ground`),
`lat`, `lon`, `alt` (ft), `gs` (kt), `track` (°), `vrate` (fpm), `squawk`, `ts` (position time),
`seen` (last contact).

Chat `parts` is a list of `{"t": text}` or `{"link": id, "t": text}`; the client renders links as
clickable focus targets. `focus` is `{kind, id}` or null.

## Controls

- Left-drag to pan, scroll wheel to zoom, left-click to select a plane or airport.
- Click empty map to clear selection. `reset` returns to the full-CONUS view.
- `pause` freezes the map (no polling, no extrapolation). The badge next to it shows how old the
  latest poll is: green, amber after 3 min, red after 10 min.
- Deep link: `#UAL1234`, `#a1b2c3` (icao24), `#DEN`.
- `?perf` in the URL logs render time per frame to the browser console.

## Where to tweak

- `templates/index.html` `:root` CSS variables: colors, panel radius, chat width, readout height.
- `static/app.js` top constants: zoom range, marker sizes, poll and extrapolation timing,
  freshness thresholds.
