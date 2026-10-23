# CONUS dashboard (Flask)

Flask port of the static `conus-dash` wireframe. Same map (D3 + us-atlas states),
focused-element readout, and chat pane, but the server now owns the data:

- the mock fleet lives in the Flask process and advances on a server clock
- the browser polls a JSON snapshot once a second and re-renders
- chat queries go to a POST endpoint and come back as structured parts

The front end is still D3 and SVG; only data loading changed.

## Run

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/flask --app app run --debug --port 8080
    # then http://localhost:8080

`python app.py` also works (debug server on port 8080).

## Layout

    app.py                 Flask routes
    conus/fleet.py         seeded fleet generator, server-side motion, chat stub
    conus/airports.py      airport table
    templates/index.html   page shell (CSS lives here)
    static/app.js          D3 map, readout, chat client
    static/geo/*.json      us-atlas states + world land TopoJSON
    static/vendor/         d3, topojson-client

## API

| Method | Path                 | Returns |
|--------|----------------------|---------|
| GET    | /api/airports        | `[[IATA, name, lat, lon], ...]` |
| GET    | /api/airlines        | `{code: name}` |
| GET    | /api/aircraft        | `{ts, motion, aircraft: [...]}` snapshot, advanced to now |
| GET    | /api/aircraft/<id>   | one aircraft |
| POST   | /api/motion          | body `{"enabled": bool}`; pauses or resumes the server clock |
| POST   | /api/chat            | body `{"q": str, "selected": {kind, id} \| null}`; returns `{parts, focus}` |

Chat `parts` is a list of `{"t": text}` or `{"link": id, "t": text}`; the client
renders links as clickable focus targets. `focus` is `{kind, id}` or null.

## Controls

- Left-drag to pan, scroll wheel to zoom, left-click to select a plane or airport.
- Click empty map to clear selection. `reset` returns to the full-CONUS view.
- `motion` toggles the server clock (affects all connected browsers).
- Chat accepts a callsign, tail number, airport code, or "who is on the ground".
- Deep link: `#UAL123`, `#N123AB`, `#DEN`.

## Where to tweak

- `templates/index.html` `:root` CSS variables: colors, panel radius, chat width, readout height.
- `static/app.js` top constants: ocean margin, zoom range, marker sizes, poll rate.
- `conus/fleet.py`: `generate()` for the mock fleet (seed, count, airlines, types);
  `Fleet.answer()` for the chat stub. Replace `Fleet` with a real feed adapter when one exists.

## Notes

- Motion is advanced lazily on each request, so there is no background thread.
  With the debug reloader the fleet state lives in the child process only.
- Fleet state is per-process. Running multiple workers (gunicorn) would give each
  its own fleet; put state in a shared store before doing that.
