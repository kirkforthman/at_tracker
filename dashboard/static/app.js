/* CONUS dashboard — map, readout, chat. Data comes from the Flask API (window.API). */
(async function () {
  // ---------- Tweak knobs ----------
  const OCEAN_PAD = 0.06;     // fraction of map size allowed as "ocean" scroll margin around CONUS
  const FIT_PAD = 24;         // px inset when fitting CONUS into the viewport
  const FIT_LEFT = 210;       // extra left inset so the filter box does not cover the Pacific Northwest
  const ZOOM_MIN = 1, ZOOM_MAX = 14;
  const LABEL_MIN_ZOOM = 1;   // show airport labels at/above this zoom (1 = always)
  const PLANE_SIZE = 13;      // triangle side length, in screen px
  const AIRPORT_R = 3.5;      // airport dot radius, screen px
  const POLL_MS = 1000;       // how often to pull a fleet snapshot from the server

  // ---------- Data ----------
  const getJSON = (url) => fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); });
  const postJSON = (url, body) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    .then(r => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); });

  const [US_STATES, WORLD_LAND, AIRPORTS, AIRLINES, snap0] = await Promise.all([
    getJSON(API.states), getJSON(API.land), getJSON(API.airports), getJSON(API.airlines), getJSON(API.aircraft)
  ]);
  const AIRCRAFT = snap0.aircraft;
  const acById = new Map(AIRCRAFT.map(a => [a.id, a]));
  const apByCode = Object.fromEntries(AIRPORTS.map(a => [a[0], a]));
  const motionBox = document.getElementById("motion");
  motionBox.checked = snap0.motion;

  // Merge a server snapshot into the local fleet in place, so object identity (and selection) survives.
  function mergeSnapshot(snap) {
    for (const n of snap.aircraft) {
      const o = acById.get(n.id);
      if (o) Object.assign(o, n); else { AIRCRAFT.push(n); acById.set(n.id, n); }
    }
    motionBox.checked = snap.motion;
  }

  // ---------- Setup ----------
  const panel = document.getElementById("mapPanel");
  const svg = d3.select("#map");
  const tip = document.getElementById("tip");
  const NON_CONUS = new Set(["02", "15", "60", "66", "69", "72", "78"]);
  const states = topojson.feature(US_STATES, US_STATES.objects.states);
  states.features = states.features.filter(f => !NON_CONUS.has(f.id));
  const mesh = topojson.mesh(US_STATES, US_STATES.objects.states, (a, b) => a !== b && !NON_CONUS.has(a.id) && !NON_CONUS.has(b.id));
  const outline = topojson.merge(US_STATES, US_STATES.objects.states.geometries.filter(g => !NON_CONUS.has(g.id)));

  const projection = d3.geoAlbers();
  const path = d3.geoPath(projection);
  let W = 0, H = 0, transform = d3.zoomIdentity, selected = null;
  const filter = { status: "", airline: "" };
  const visible = (p) => (!filter.status || p.status === filter.status) && (!filter.airline || p.airline === filter.airline);

  const root = svg.append("g").attr("class", "root");
  const gWorld = root.append("path").attr("class", "world");
  const worldLand = topojson.feature(WORLD_LAND, WORLD_LAND.objects.land);
  const gStates = root.append("g");
  const gBorders = root.append("path").attr("class", "state").style("fill", "none");
  const gRoute = root.append("path").attr("class", "route");
  const gAirports = root.append("g");
  const gPlanes = root.append("g");

  gStates.selectAll("path").data(states.features).join("path").attr("class", "state")
    .append("title").text(d => d.properties.name);

  const zoom = d3.zoom().scaleExtent([ZOOM_MIN, ZOOM_MAX]).on("zoom", (ev) => { transform = ev.transform; render(); });
  svg.call(zoom).on("dblclick.zoom", null);
  svg.on("click", (ev) => { hidePicker(); if (ev.target === svg.node() || ev.target.classList.contains("state")) select(null); });

  function layout() {
    W = panel.clientWidth; H = panel.clientHeight;
    svg.attr("viewBox", `0 0 ${W} ${H}`);
    projection.fitExtent([[FIT_LEFT, FIT_PAD], [W - FIT_PAD, H - FIT_PAD]], outline);
    const padX = W * OCEAN_PAD, padY = H * OCEAN_PAD;
    zoom.translateExtent([[-padX, -padY], [W + padX, H + padY]]);
    gWorld.attr("d", path(worldLand));
    gStates.selectAll("path").attr("d", path);
    gBorders.attr("d", path(mesh));
    for (const a of AIRPORTS) a.xy = projection([a[3], a[2]]);
    render();
  }

  // ---------- Positions ----------
  function planeXY(p) {
    const o = apByCode[p.origin].xy, d = apByCode[p.dest].xy;
    if (p.status === "ground") return o;
    return [o[0] + (d[0] - o[0]) * p.progress, o[1] + (d[1] - o[1]) * p.progress];
  }
  function headingDeg(p) {
    const o = apByCode[p.origin].xy, d = apByCode[p.dest].xy;
    return (Math.atan2(d[0] - o[0], -(d[1] - o[1])) * 180 / Math.PI + 360) % 360;
  }
  function planeLL(p) { return projection.invert(planeXY(p)); }

  // ---------- Render ----------
  function render() {
    const t = transform, k = t.k;
    root.attr("transform", t);
    document.getElementById("zoomLabel").textContent = `zoom ${k.toFixed(1)}×`;

    const showLabels = k >= LABEL_MIN_ZOOM;
    gAirports.selectAll("g.airport").data(AIRPORTS, d => d[0]).join(
      enter => {
        const g = enter.append("g").attr("class", "airport").on("click", (ev, d) => { ev.stopPropagation(); select({ kind: "airport", data: d }); })
          .on("mousemove", (ev, d) => showTip(ev, `${d[0]} · ${d[1]}`)).on("mouseleave", hideTip);
        g.append("circle"); g.append("text").attr("dy", -6).attr("text-anchor", "middle").text(d => d[0]);
        return g;
      })
      .attr("transform", d => `translate(${d.xy[0]},${d.xy[1]}) scale(${1 / k})`)
      .classed("selected", d => selected && selected.kind === "airport" && selected.data === d)
      .select("circle").attr("r", AIRPORT_R);
    gAirports.selectAll("text").style("display", showLabels ? null : "none");

    const s = PLANE_SIZE;
    gPlanes.selectAll("g.plane").data(AIRCRAFT, d => d.id).join(
      enter => {
        const g = enter.append("g").on("click", (ev, d) => { ev.stopPropagation(); hideTip(); onPlaneClick(ev, d); })
          .on("mousemove", (ev, d) => showTip(ev, `${d.callsign} ${d.status === "flight" ? "FL" + d.alt / 100 : "GND"}`)).on("mouseleave", hideTip);
        const h = s * Math.sqrt(3) / 2;
        g.append("circle").attr("class", "halo").attr("r", s * 0.75 + 4);
        g.append("polygon").attr("points", `0,${-2 * h / 3} ${s / 2},${h / 3} ${-s / 2},${h / 3}`);
        return g;
      })
      .attr("class", d => `plane ${d.status}`)
      .style("display", d => visible(d) ? null : "none")
      .classed("selected", d => selected && selected.kind === "aircraft" && selected.data === d)
      .attr("transform", d => { const [x, y] = planeXY(d); return `translate(${x},${y}) scale(${1 / k})`; })
      .select("polygon").attr("transform", d => `rotate(${headingDeg(d)})`);

    if (selected && selected.kind === "aircraft" && selected.data.status === "flight") {
      const p = selected.data, o = apByCode[p.origin].xy, d = apByCode[p.dest].xy;
      gRoute.attr("d", `M${o[0]},${o[1]}L${d[0]},${d[1]}`).style("display", null);
    } else gRoute.style("display", "none");

    const shown = AIRCRAFT.filter(visible), ground = shown.filter(a => a.status === "ground").length;
    const filtered = filter.status || filter.airline;
    document.getElementById("counts").textContent = `${shown.length - ground} airborne · ${ground} on ground` + (filtered ? ` (${shown.length}/${AIRCRAFT.length})` : "");
  }

  function showTip(ev, text) {
    const r = panel.getBoundingClientRect();
    tip.textContent = text; tip.style.display = "block";
    tip.style.left = (ev.clientX - r.left) + "px"; tip.style.top = (ev.clientY - r.top) + "px";
  }
  function hideTip() { tip.style.display = "none"; }

  // ---------- Stacked-aircraft picker ----------
  const picker = document.getElementById("picker");
  function hidePicker() { picker.style.display = "none"; }
  function onPlaneClick(ev, d) {
    const stack = d.status === "ground" ? AIRCRAFT.filter(p => p.status === "ground" && p.origin === d.origin && visible(p)) : [d];
    if (stack.length < 2) { hidePicker(); select({ kind: "aircraft", data: d }); return; }
    const r = panel.getBoundingClientRect();
    picker.innerHTML = `<div class="ph">${stack.length} aircraft at ${d.origin}</div>` + stack.map(p =>
      `<div class="pi${selected && selected.data === p ? " active" : ""}" data-id="${p.id}"><span class="sw"></span><span class="cs">${p.callsign}</span><span class="meta">${p.type} · ${p.reg} · to ${p.dest}</span></div>`).join("");
    picker.querySelectorAll(".pi").forEach(el => el.addEventListener("click", (e) => {
      e.stopPropagation(); hidePicker(); select({ kind: "aircraft", data: acById.get(el.dataset.id) });
    }));
    picker.style.display = "block";
    let x = ev.clientX - r.left + 10, y = ev.clientY - r.top + 10;
    if (x + picker.offsetWidth > r.width - 8) x = r.width - picker.offsetWidth - 8;
    if (y + picker.offsetHeight > r.height - 8) y = Math.max(8, ev.clientY - r.top - picker.offsetHeight - 10);
    picker.style.left = x + "px"; picker.style.top = y + "px";
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hidePicker(); });
  svg.on("mousedown.picker", hidePicker).on("wheel.picker", hidePicker);

  // ---------- Selection + readout ----------
  function select(sel) { selected = sel; render(); renderReadout(); }
  function selectedRef() { return selected ? { kind: selected.kind, id: selected.kind === "aircraft" ? selected.data.id : selected.data[0] } : null; }
  function fmtLL([lon, lat]) { return `${lat.toFixed(3)}, ${lon.toFixed(3)}`; }
  function field(k, v) { return `<div class="field"><div class="k">${k}</div><div class="v" title="${v}">${v}</div></div>`; }
  function renderReadout() {
    const el = document.getElementById("readout");
    if (!selected) { el.innerHTML = `<div class="read-empty">Click an aircraft or airport on the map to see its data here.</div>`; return; }
    if (selected.kind === "airport") {
      const a = selected.data;
      const here = AIRCRAFT.filter(p => p.status === "ground" && p.origin === a[0]).length;
      const inbound = AIRCRAFT.filter(p => p.status === "flight" && p.dest === a[0]).length;
      el.innerHTML = `<div class="read-head"><h2>${a[0]}</h2><span class="sub">${a[1]}</span><span class="badge airport">airport</span></div>
        <div class="fields">${field("IATA", a[0])}${field("Position", fmtLL([a[3], a[2]]))}${field("On ground", here)}${field("Inbound", inbound)}${field("Outbound", AIRCRAFT.filter(p => p.status === "flight" && p.origin === a[0]).length)}${field("Status", "OPEN")}</div>`;
      return;
    }
    const p = selected.data, fl = p.status === "flight";
    el.innerHTML = `<div class="read-head"><h2>${p.callsign}</h2><span class="sub">${p.reg} · ${p.type}</span><span class="badge ${p.status}">${fl ? "in flight" : "on ground"}</span></div>
      <div class="fields">
        ${field("Origin", p.origin)}${field("Destination", p.dest)}${field("Altitude", fl ? p.alt.toLocaleString() + " ft" : "—")}
        ${field("Ground speed", p.gs + " kt")}${field("Heading", Math.round(headingDeg(p)).toString().padStart(3, "0") + "°")}${field("Squawk", p.squawk)}
        ${field("Position", fmtLL(planeLL(p)))}${field("Progress", fl ? Math.round(p.progress * 100) + "%" : "at gate")}${field("Registration", p.reg)}
        ${field("Type", p.type)}${field("Last seen", lastSeen.toLocaleTimeString())}${field("Source", "flask · mock")}
      </div>`;
  }

  function focusOn(p) {
    const [x, y] = p.kind === "airport" ? p.data.xy : planeXY(p.data);
    const k = Math.max(transform.k, 4);
    svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity.translate(W / 2 - x * k, H / 2 - y * k).scale(k));
    select(p);
  }
  function focusRef(ref) {
    if (!ref) return;
    if (ref.kind === "aircraft" && acById.has(ref.id)) focusOn({ kind: "aircraft", data: acById.get(ref.id) });
    else if (ref.kind === "airport" && apByCode[ref.id]) focusOn({ kind: "airport", data: apByCode[ref.id] });
  }

  // ---------- Motion: server owns the clock, client polls ----------
  let lastSeen = new Date(snap0.ts * 1000);
  let polling = false;
  async function poll() {
    if (polling) return; polling = true;
    try {
      const snap = await getJSON(API.aircraft);
      mergeSnapshot(snap); lastSeen = new Date(snap.ts * 1000);
      setLink(true);
      render(); if (selected) renderReadout();
    } catch (e) { setLink(false); }
    finally { polling = false; }
  }
  setInterval(poll, POLL_MS);
  motionBox.addEventListener("change", async () => {
    try { const r = await postJSON(API.motion, { enabled: motionBox.checked }); motionBox.checked = r.motion; }
    catch (e) { setLink(false); }
  });
  let linkUp = true;
  function setLink(up) { if (up === linkUp) return; linkUp = up; say("sys", up ? "backend reconnected" : "backend unreachable — retrying"); }

  // ---------- Chat (server stub) ----------
  const log = document.getElementById("chatLog");
  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function say(cls, html) {
    const m = document.createElement("div"); m.className = "msg " + cls; m.innerHTML = html; log.appendChild(m); log.scrollTop = log.scrollHeight;
    m.querySelectorAll("a[data-id]").forEach(a => a.addEventListener("click", () => {
      const id = a.dataset.id;
      focusRef(acById.has(id) ? { kind: "aircraft", id } : { kind: "airport", id });
    }));
  }
  const link = (id, text) => `<a data-id="${esc(id)}">${esc(text)}</a>`;
  const partsToHtml = (parts) => parts.map(p => p.link ? link(p.link, p.t) : esc(p.t)).join("");
  async function ask(q) {
    try {
      const r = await postJSON(API.chat, { q, selected: selectedRef() });
      focusRef(r.focus);
      say("bot", partsToHtml(r.parts));
    } catch (e) { say("sys", "chat request failed: " + esc(e.message)); }
  }
  document.getElementById("chatForm").addEventListener("submit", (ev) => {
    ev.preventDefault(); const inp = document.getElementById("chatText"); const q = inp.value.trim(); if (!q) return;
    say("user", esc(q)); inp.value = "";
    ask(q);
  });
  say("sys", "flask backend · mock fleet");
  say("bot", `Hi. Ask about an aircraft by callsign or an airport by code, e.g. ${link(AIRCRAFT[0].id, AIRCRAFT[0].callsign)} or ${link("DEN", "DEN")}.`);

  // ---------- Filters ----------
  const fAirline = document.getElementById("fAirline");
  for (const code of Object.keys(AIRLINES).sort()) {
    const o = document.createElement("option"); o.value = code; o.textContent = `${AIRLINES[code]} (${code})`; fAirline.appendChild(o);
  }
  function applyFilters() {
    filter.status = document.getElementById("fStatus").value;
    filter.airline = fAirline.value;
    hidePicker();
    if (selected && selected.kind === "aircraft" && !visible(selected.data)) selected = null;
    render(); renderReadout();
  }
  document.getElementById("fStatus").addEventListener("change", applyFilters);
  fAirline.addEventListener("change", applyFilters);

  // ---------- Boot ----------
  document.getElementById("resetView").addEventListener("click", () => svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity));
  new ResizeObserver(layout).observe(panel);
  layout();
  // Deep link: #UAL123, #N123AB, #DEN selects + focuses on load.
  const applyHash = () => { const h = decodeURIComponent(location.hash.slice(1)); if (h) ask(h); };
  window.addEventListener("hashchange", applyHash);
  applyHash();
})().catch(err => {
  console.error(err);
  const el = document.getElementById("readout");
  if (el) el.innerHTML = `<div class="read-empty">Failed to load data from the server: ${String(err.message).replace(/</g, "&lt;")}</div>`;
});
