// The city as a real 3D model (style `model`, kit city3d-kit.js): every OpenStreetMap building
// extruded to its height over the real street plan, filling the frame; the camera flies through it on
// one continuous path (Catmull-Rom through the shots' key views, so cuts never jump). History is light:
// era extents glow in their colours while the rest of the city dims, a halo sweeps out when an era
// begins, ended eras stay as fine rings, walls glow while built, landmarks light their own buildings.
// params per shot:
//   year: [y0, y1]                        the year block reads from y0 to y1
//   path: [prev, from, to, next]          key views { x, y, d, pitch, yaw, fov } (km, degrees); the
//                                         shot flies from → to; prev/next keep the motion smooth across
//                                         cuts (use the neighbouring shots' views, null at the ends)
//   globe: { lat, lon, km: [k0, k1] }     globe flight from k0 km of visible width (globe, flat map
//                                         and 3D share one scale; ~32000 shows the whole globe)
//   grow: [g0, g1]                        building heights scale (0 = flat plan, 1 = full)
//   dim: [d0, d1]                         0 = bright plaster model, ~0.55 = dimmed stage for the light
//   halo: { area, beat }                  white ring sweeping out from an era's extent
//   focus: [{ id, beat }]                 chronology.focus item; kind "scar" tints a fire or a sack
//   heights: true                         buildings coloured by height with the tallest one measured
//   tint: [t0, t1]                        height colours fading in or out (smooth hand-over to and from
//                                         a heights shot)
//   rings: true                           every era's ring with its name and first year
//   big: { text, unit?, line?, note? }    a figure instead of the year in the left block
//   era_label: true                       name the current extent
//   clean: true                           the bare model: no rings, labels or year
//   morph: { from, to, beat?, beats? }    the outline of one era's extent slides to the next, with
//                                         arrows and "The city grows / shrinks" (from the areas' km²)
//   spread: [{ from, area?, r_km, color?, kind?: 'fire', beat?, beats? }]
//                                         streets light up outward from a place, street by street
//   found: { place, beat? }               a column of light and ripples where the city began
//   river: true | { keep }                the main river brightens from upstream, light runs downstream
// first key view of a shot's path
const strHash = (t) => { let h = 2166136261; for (const c of String(t)) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0; return (h % 99991) + 1 }
const path0 = (p) => (p.path && p.path[1]) || {}
const trapez = (t, a = 0.2) => (t <= 0 ? 0 : t >= 1 ? 1 : t < a ? (t * t) / (2 * a * (1 - a)) : t > 1 - a ? 1 - ((1 - t) * (1 - t)) / (2 * a * (1 - a)) : (t - a / 2) / (1 - a))
const inRing = (x, y, ring) => { let c = false; for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) { const a = ring[i], b = ring[j]; if ((a[1] > y) !== (b[1] > y) && x < ((b[0] - a[0]) * (y - a[1])) / (b[1] - a[1]) + a[0]) c = !c } return c }
// streets and roads near a place, sorted by distance (km) from it; memoised per place, area and radius
const SPREAD = new Map()
const spreadLines = (geo, at, area, rMax) => {
  const key = `${at.x},${at.y}|${area ? area.id : ''}|${rMax}`
  if (SPREAD.has(key)) return SPREAD.get(key)
  const out = []
  for (const ln of [...(geo.roads || []), ...(geo.streets || [])]) {
    const pts = ln.pts || ln
    let d = Infinity
    for (const q of pts) d = Math.min(d, Math.hypot(q[0] - at.x, q[1] - at.y))
    if (d > rMax) continue
    if (area && area.ring && !pts.some((q) => inRing(q[0], q[1], area.ring))) continue
    out.push({ pts, d })
  }
  out.sort((a, b) => a.d - b.d)
  SPREAD.set(key, out)
  return out
}
// rays for an extent morph, memoised: points every ~0.15 km along the outer outline, each with its
// nearest point on the seed outline (n), the distance d (0 when inside the seed) and the unit direction
const RAYS = new Map()
const morphRays = (seed, outer) => {
  const key = `${seed.id}>${outer.id}`
  if (RAYS.has(key)) return RAYS.get(key)
  const ring = outer.ring, pts = []
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i], b = ring[(i + 1) % ring.length], n = Math.max(1, Math.round(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.15))
    for (let t = 0; t < n; t++) pts.push([a[0] + ((b[0] - a[0]) * t) / n, a[1] + ((b[1] - a[1]) * t) / n])
  }
  const sr = seed.ring, out = []
  pts.forEach((p, idx) => {
    if (idx % 2) return
    if (inRing(p[0], p[1], sr)) { out.push({ p, n: p, d: 0, ux: 0, uy: 0 }); return }
    let best = null, bd = Infinity
    for (let i = 0; i < sr.length; i++) {
      const a = sr[i], b = sr[(i + 1) % sr.length], dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy || 1
      const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)), q = [a[0] + dx * t, a[1] + dy * t], d = Math.hypot(p[0] - q[0], p[1] - q[1])
      if (d < bd) { bd = d; best = q }
    }
    out.push({ p, n: best, d: bd, ux: (p[0] - best[0]) / bd, uy: (p[1] - best[1]) / bd })
  })
  RAYS.set(key, out)
  return out
}
// a named river's OSM pieces joined end to end (pieces run downstream), memoised
const RIVERS = new Map()
const riverByName = (geo, name) => {
  if (RIVERS.has(name)) return RIVERS.get(name)
  const re = new RegExp(name, 'i'), parts = (geo.rivers || []).filter((x) => !x.canal && re.test(x.name || '')).map((x) => x.pts)
  const near = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) < 0.05
  let start = parts.find((pp) => !parts.some((o) => o !== pp && near(o[o.length - 1], pp[0]))) || parts[0]
  const pts = start ? start.slice() : [], used = new Set([start])
  for (let guard = 0; guard < parts.length; guard++) {
    const nx = parts.find((o) => !used.has(o) && near(pts[pts.length - 1], o[0]))
    if (!nx) break
    used.add(nx); pts.push(...nx.slice(1))
  }
  const rv = pts.length >= 2 ? { name, pts } : null
  RIVERS.set(name, rv)
  return rv
}
// a river as arc length → point and unit tangent, in its own point order (OSM rivers run downstream)
const RIVER = new Map()
const riverOf = (rv) => {
  if (RIVER.has(rv)) return RIVER.get(rv)
  const pts = rv.pts, cum = [0]
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
  const L = cum[cum.length - 1] || 1
  const at = (d) => {
    let lo = 1, hi = cum.length - 1
    while (lo < hi) { const m = (lo + hi) >> 1; if (cum[m] < d) lo = m + 1; else hi = m }
    const i = Math.max(1, lo), sl = (cum[i] - cum[i - 1]) || 1, f = (d - cum[i - 1]) / sl
    const tx = (pts[i][0] - pts[i - 1][0]) / sl, ty = (pts[i][1] - pts[i - 1][1]) / sl
    return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f, tx, ty]
  }
  const f = { L, at }
  RIVER.set(rv, f)
  return f
}
scene('city-3d', function (g, s) {
  const k = s.kit, C3 = k.city3d
  const W = s.W, H = s.H, p = s.params, geo = s.geo
  const ch = (geo && geo.chronology) || {}
  const lang = s.lang
  const u = k.clamp(s.u, 0, 1), e = k.ease.inOut(u)
  const yr = Array.isArray(p.year) ? p.year : [p.year ?? 2026, p.year ?? 2026]
  const year = yr[0] + (yr[1] - yr[0]) * u
  const layers = ch.layers || []
  g.fillStyle = '#08080A'; g.fillRect(0, 0, W, H)
  // the left, bottom and top shades sit on every frame (also over the globe), so they never pop in
  const shades = () => {
    const back = g.createLinearGradient(0, 0, W * 0.32, 0)
    back.addColorStop(0, 'rgba(6,6,7,0.7)'); back.addColorStop(1, 'rgba(6,6,7,0)')
    g.fillStyle = back; g.fillRect(0, 0, W * 0.32, H)
    const low = g.createLinearGradient(0, H * 0.78, 0, H)
    low.addColorStop(0, 'rgba(6,6,7,0)'); low.addColorStop(1, 'rgba(6,6,7,0.65)')
    g.fillStyle = low; g.fillRect(0, H * 0.78, W, H * 0.22)
    const topShade = g.createLinearGradient(0, 0, 0, H * 0.14)
    topShade.addColorStop(0, 'rgba(6,6,7,0.55)'); topShade.addColorStop(1, 'rgba(6,6,7,0)')
    g.fillStyle = topShade; g.fillRect(0, 0, W, H * 0.14)
  }
  // ---- opening: the globe turns to the city, a flat map takes over (no horizon flicker), then the
  //      3D city dissolves in at the same scale and the camera carries on down the path ----
  let cityA = 1, pathU = u, d0 = null
  if (p.globe && geo) {
    // visible width per unit of camera distance (fov is vertical), so the 2D maps and the 3D city share one scale
    const kw = 2 * Math.tan(((path0(p).fov || 34) * Math.PI) / 360) * (W / H)
    const c = geo.center, [k0] = p.globe.km, kEnd = (path0(p).d || 50) * kw
    const rot = k.ease.inOut(k.prog(u, 0, 0.3))
    // zoom in log space with a trapezoid speed profile (speeds up over the first fifth, steady, slows
    // over the last fifth): the fastest frame is only 1.25× the average, so the globe-to-map hand-over
    // does not jump, and it still starts and stops at rest
    const zt = k.prog(u, 0.12, 0.8)
    const km = Math.exp(Math.log(k0) + (Math.log(kEnd) - Math.log(k0)) * trapez(zt))
    const lat = p.globe.lat + (c.lat - p.globe.lat) * rot, lon = p.globe.lon + (c.lon - p.globe.lon) * rot
    const flatA = k.clamp((1800 - km) / 600, 0, 1)
    if (flatA < 1) k.globe(g, s, { R: (W / km) * 6371, lat, lon, alpha: 1, pin: rot > 0.9 && km > 6000 ? { lat: c.lat, lon: c.lon, label: k.labelOf(ch.city, lang), sub: ch.coords || '' } : null })
    if (flatA > 0) {
      const dark = k.clamp(Math.log(1500 / km) / Math.log(1500 / (kEnd * 2.5)), 0, 1)
      k.flatMap(g, s, { km, lat, lon, alpha: flatA, dark, local: { lat: c.lat, lon: c.lon } })
      // the city's pin stays on the map until the 3D model takes over
      g.save(); g.globalAlpha = flatA * k.clamp((km - kEnd * 3) / kEnd, 0, 1); g.fillStyle = k.PAL.gold || '#E8C27A'; g.beginPath(); g.arc(W / 2, H / 2, 6, 0, Math.PI * 2); g.fill(); g.restore()
    }
    cityA = k.clamp((kEnd * 2.2 - km) / (kEnd * 1.2), 0, 1)
    pathU = k.prog(u, 0.8, 1)
    if (u < 0.8) d0 = km / kw
    if (cityA <= 0) { shades(); k.hud(g, s, ch.hud || [], 0.85); return }
  }
  // ---- camera on the continuous path ----
  const path = p.path || [null, ch.camera, ch.camera, null]
  const view = C3.pathView(path[0], path[1], path[2], path[3], pathU)
  if (d0 != null) view.d = d0
  const cam = C3.camera(view, W, H)
  const R = ch.ground_km || 5
  let gl = s.gl('city', W, H, (ctx) => C3.init(ctx, geo, { R, exaggerate: ch.height_exaggerate || 1.6, layers, ...C3.life(geo, ch) }))
  if (!gl) return
  const win = (from, to, f) => k.window01(year, from, to, f)
  const areas = Object.fromEntries((geo.areas || []).map((x) => [x.id, x]))
  // a layer that enters through a morph has no fade-in (the morph is its entrance) and no light before
// its first year; once it has entered, the extents it replaced go dark (no old colour coming back)
  const winL = (L) => (L.morph && year < L.from ? 0 : win(L.from, L.to, L.fade ?? 30))
  const replaced = (L) => !L.spot && layers.some((M) => M !== L && M.morph && M.from > L.from && year >= M.from) && !(p.morph && p.morph.from === L.area)
  const eraA = layers.map((L) => (p.clean || p.heights || p.rings || replaced(L) ? 0 : winL(L)))
  // `found.reveal` (a founding shot right after bare-model shots): its first extent comes up with the
  // column of light instead of popping in at the cut
  const foundIn = p.found && p.found.reveal ? k.prog(s.beat, p.found.beat ?? 0.5, (p.found.beat ?? 0.5) + 1) : 1
  // (only extents that begin in this shot; one already lit, such as an earlier settlement, stays)
  for (let i = 0; i < eraA.length; i++) if (layers[i].from >= Math.min(yr[0], yr[1])) eraA[i] *= foundIn
  const lerp = (a) => (Array.isArray(a) ? a[0] + (a[1] - a[0]) * k.ease.inOut(k.prog(u, 0.1, 0.9)) : a)
  const anyEra = Math.max(0, ...eraA)
  const dim = p.dim ? lerp(p.dim) : p.clean ? 0 : 0.5
  let halo = null
  if (p.halo && areas[p.halo.area]) {
    const A = areas[p.halo.area], hp = k.prog(s.beat, p.halo.beat ?? 0, (p.halo.beat ?? 0) + 3)
    if (hp > 0 && hp < 1) { const r0 = Math.sqrt(A.km2 / Math.PI); halo = { x: A.x, y: A.y, r: r0 * (0.8 + 2.4 * k.ease.out(hp)), w: 0.06 + 0.12 * hp }; halo.w *= Math.sin(Math.PI * hp) + 0.01 }
  }
  const byId = Object.fromEntries([...(geo.places || []), ...(geo.hills || [])].map((x) => [x.id, x]))
  let focus = null, scar = null, sink = null
  for (const f of p.focus || []) {
    const F = (ch.focus || {})[f.id], at = F && byId[F.place]
    if (!at) continue
    const last = s.dur / s.beat_s, a = k.prog(s.beat, f.beat || 0, (f.beat || 0) + 1) * (F.collapse ? 1 : 1 - k.prog(s.beat, last - 0.5, last))
    if (F.kind === 'scar') scar = { x: at.x, y: at.y, r: (F.ring_km || 0.6) * k.ease.out(k.prog(s.beat, f.beat || 0, (f.beat || 0) + 2)), a }
    if (F.kind === 'scar' && F.collapse) sink = { x: at.x, y: at.y, r: scar.r, a: k.ease.inOut(k.prog(s.beat, (f.beat || 0) + 0.4, (f.beat || 0) + 3)) }
    else focus = { x: at.x, y: at.y, r: Math.max(0.06, F.r_km || 0.1), a }
  }
  // rebuild: the burnt area of an earlier shot fades back and its buildings rise again
  if (p.rebuild) {
    const F = (ch.focus || {})[p.rebuild.id], at = F && byId[F.place]
    if (at) { const rb = k.ease.inOut(k.prog(s.beat, p.rebuild.beat ?? 0.2, (p.rebuild.beat ?? 0.2) + (p.rebuild.beats ?? 3))); scar = { x: at.x, y: at.y, r: F.ring_km || 0.6, a: 1 - rb }; sink = { x: at.x, y: at.y, r: F.ring_km || 0.6, a: 1 - rb } }
  }
  // extent morph: the growing era's light (or the shrinking one's) follows the sliding outline
  let reveal = null, morphP = null
  if (p.morph && !p.rings && areas[p.morph.from] && areas[p.morph.to] && areas[p.morph.from].ring && areas[p.morph.to].ring) {
    const A0 = areas[p.morph.from], A1 = areas[p.morph.to], b0 = p.morph.beat ?? 0.3
    const mp = k.ease.inOut(k.prog(s.beat, b0, b0 + (p.morph.beats ?? 3))), grows = (A1.km2 || 0) >= (A0.km2 || 0)
    morphP = mp
    const li = layers.findIndex((L) => L.area === (grows ? p.morph.to : p.morph.from))
    if (li >= 0) {
      // growing: the new era's light spreads out of the old extent; shrinking: the old era's light
      // withdraws into the new one. Either way it moves at one speed and follows the real outlines.
      const seed = grows ? A0 : A1, target = grows ? A1 : A0
      reveal = { key: `${seed.id}>${target.id}`, seed: seed.ring, target: target.ring, p: grows ? mp : 1 - mp, layer: li, active: mp > 0 && mp < 1 }
      eraA[li] = grows ? Math.max(eraA[li], 1) : Math.max(eraA[li], 1 - k.prog(mp, 0.97, 1))
      // when the city grows, the older era inside takes the new colour as the light spreads
      const lf = layers.findIndex((L) => L.area === p.morph.from)
      if (grows && lf >= 0 && !layers[lf].spot) eraA[lf] *= 1 - k.prog(mp, 0.5, 1)
    }
  }
  const grow = p.grow ? lerp(p.grow) : 1
  const lifeYear = p.rewind ? p.rewind[0] + (p.rewind[1] - p.rewind[0]) * k.ease.inOut(k.prog(u, 0.3, 0.97)) : year
  const frame = {
    cam, era: eraA, dim: p.dim ? dim : p.heights ? 0 : p.clean ? 0 : dim * (0.6 + 0.4 * Math.min(1, anyEra)), bright: p.clean && !p.dim ? 1.08 : 1, halo, focus, scar,
    heightTint: p.tint ? lerp(p.tint) : p.heights ? 1 : 0, scaleZ: grow, reveal, sink, year: lifeYear, t: s.t + (s.shot.start || 0), fog: [0.03, 0.03, 0.035], fogNear: view.d * 1.1, fogFar: view.d * 4.2,
}
  // a lost software context is rebuilt once instead of leaving a black frame
  for (let attempt = 0; attempt < 2; attempt++) {
    // the first draw after building the GL state can come out without its ground texture (the upload
    // and mipmaps are still settling), so a fresh state draws once to warm up before the real frame
    if (!gl.state.warm) { C3.draw(gl.gl, gl.state, frame); gl.gl.finish(); gl.state.warm = true }
    C3.draw(gl.gl, gl.state, frame)
    if (!gl.gl.isContextLost()) break
    gl = s.gl('city', W, H, (ctx) => C3.init(ctx, geo, { R, exaggerate: ch.height_exaggerate || 1.6, layers, ...C3.life(geo, ch) }))
  }

  g.save(); g.globalAlpha = cityA; g.drawImage(gl.canvas, 0, 0); g.restore()
  // ---- overlays (same camera) ----
  const P = (x, y, z) => cam.project(x, y, z || 0)
  const ringPath = (pts) => { const pa = new Path2D(); let pen = false; for (const pt of pts) { const q = P(pt[0], pt[1]); if (q[2] < 0) { pen = false; continue } if (pen) pa.lineTo(q[0], q[1]); else { pa.moveTo(q[0], q[1]); pen = true } } return pa }
  const closed = (pts) => pts.concat([pts[0]])
  const byIdAll = Object.fromEntries([...(geo.places || []), ...(geo.hills || [])].map((x) => [x.id, x]))
  const T = s.t + (s.shot.start || 0)
  const taken = []
  // points spaced along a polyline (km), deterministic per key
  const sampleAlong = (pts, count, key) => {
    const cum = [0]; for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    const L0 = cum[cum.length - 1] || 1, rr = k.rng(strHash(key)), out = []
    for (let c = 0; c < count; c++) { const d = rr() * L0; let i = 1; while (i < cum.length - 1 && cum[i] < d) i++; const t2 = (d - cum[i - 1]) / ((cum[i] - cum[i - 1]) || 1); out.push([pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t2, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t2, rr(), rr()]) }
    return out
  }
  // sparks rising off a line: ph 0..1 is the life of the effect
  const embersAlong = (pts, ph, color, count, key) => {
    const a0 = Math.sin(Math.PI * ph)
    g.save()
    for (const [x, y, r1, r2] of sampleAlong(pts, count, key)) {
      const lift = ((ph * 1.6 + r1) % 1), q0 = P(x, y, 0.004 + lift * 0.06)
      if (q0[2] < 0) continue
      g.globalAlpha = a0 * (1 - lift) * (0.5 + 0.5 * r2)
      g.fillStyle = r2 > 0.6 ? '#FFE2B0' : color
      g.beginPath(); g.arc(q0[0] + Math.sin(T * 3 + r1 * 20) * 3, q0[1], 1.2 + 2.2 * r2 * (1 - lift), 0, Math.PI * 2); g.fill()
    }
    g.restore()
  }
  const burst = (q, ph, color, count, key, sc = 1) => {
    const rr = k.rng(strHash(key + 'b'))
    g.save()
    for (let i = 0; i < count; i++) { const a = rr() * Math.PI * 2, sp = (40 + rr() * 160) * sc, d = k.ease.out(ph) * sp; g.globalAlpha = (1 - ph) * (0.5 + 0.5 * rr()); g.fillStyle = rr() > 0.5 ? '#FFE6C0' : color; g.beginPath(); g.arc(q[0] + Math.cos(a) * d, q[1] + Math.sin(a) * d * 0.6 - ph * 40 * sc * rr(), (1.5 + 2.5 * rr()) * Math.sqrt(sc), 0, Math.PI * 2); g.fill() }
    const rg = (20 + 120 * k.ease.out(ph)) * sc; g.globalAlpha = (1 - ph) * 0.8; g.strokeStyle = color; g.lineWidth = 2 * Math.sqrt(sc); g.beginPath(); g.ellipse(q[0], q[1], rg, rg * 0.55, 0, 0, Math.PI * 2); g.stroke()
    g.restore()
  }
  g.save(); g.globalAlpha = cityA
  if (!p.clean && !p.heights) {
    for (const L of layers) {
      const A = areas[L.area]
      if (!A || !A.ring) continue
      const vis = winL(L)
      const ended = year >= L.to - 10 || p.rings
      if (ended && !L.spot) { g.save(); g.globalAlpha *= p.rings ? 0.6 + 0.3 * k.prog(s.beat, 0.3, 2) : 0.6 * k.clamp((year - L.to + 10) / 30, 0, 1); g.strokeStyle = 'rgba(255,255,255,0.9)'; g.lineWidth = 1.4; g.stroke(ringPath(closed(A.ring))); g.restore() }
      // during a morph the new edge only lights once the light reaches it; the old one goes at once
      const mv = morphP == null ? 1 : L.area === p.morph.to ? k.prog(morphP, 0.92, 1) : L.area === p.morph.from ? 0 : 1
      const fi = L.from >= Math.min(yr[0], yr[1]) ? foundIn : 1
      if (!p.rings && vis * mv * fi > 0 && !L.spot) k.glowEdge(g, ringPath(closed(A.ring)), L.color, vis * mv * fi)
    }
    // walls: rise as a glowing line while built, then a fine bright line; `until` dissolves the whole wall
    // into embers, `breach: { place, year, r_km }` blows a gap open at a place
    for (const w of ch.walls || []) {
      const Wd = (geo.walls || []).find((x) => x.id === w.id)
      const wf = p.rings ? 1 - k.prog(s.beat, 0.2, 2) : 1
      if (!Wd || year < w.from || wf <= 0) continue
      const prog = k.clamp((year - w.from) / Math.max(1, w.to - w.from), 0, 1)
      // the wall glows while it is new, and flares again around its breach year, so a breached wall
      // stands out even where it runs along an era's lit edge
      const glow = Math.max(1 - k.clamp((year - w.to - (w.glow_years ?? 60)) / 60, 0, 1), w.breach ? k.clamp(1 - Math.abs(year - w.breach.year) / 12, 0, 1) : 0)
      const gone = w.until != null ? k.clamp((year - w.until) / (w.dissolve_years ?? 40), 0, 1) : 0
      if (gone >= 1) continue
      const br = w.breach, bAt = br && byIdAll[br.place], bp = br ? k.clamp((year - br.year) / 6, 0, 1) : 0
      const n = Math.ceil(Wd.segments.length * prog)
      const keep = (seg) => !(bAt && bp > 0 && seg.some((pt) => Math.hypot(pt[0] - bAt.x, pt[1] - bAt.y) < (br.r_km || 0.12)))
      g.save(); g.globalAlpha *= wf; g.lineCap = 'round'; g.lineJoin = 'round'
      const flare = gone > 0 ? Math.sin(Math.PI * Math.min(1, gone * 1.4)) : 0
      for (const [wd, al] of [[14, 0.14 * glow + 0.3 * flare], [6, 0.35 * glow + 0.4 * flare], [2.5, 0.5 + 0.5 * glow]]) {
        g.strokeStyle = k.rgba(w.color || '#FF5A43', al * (1 - gone)); g.lineWidth = wd
        for (let i2 = 0; i2 < n; i2++) if (keep(Wd.segments[i2])) g.stroke(ringPath(Wd.segments[i2]))
      }
      g.restore()
      if (gone > 0) embersAlong(Wd.segments.flat(), gone, w.color || '#FF7A4D', 90, w.id)
      if (bAt && bp > 0 && bp < 1) { const q = P(bAt.x, bAt.y); if (q[2] > 0) burst(q, bp, '#FFB066', 120, w.id, 1.8) }
    }
  }
  // streets light up outward from a place, street by street (the city spreading, or a fire running
  // through it); `area` keeps the spread inside an era's extent
  for (const sp of p.spread || []) {
    const at = byIdAll[sp.from]; if (!at) continue
    const b0 = sp.beat ?? 0.3, pr = k.ease.inOut(k.prog(s.beat, b0, b0 + (sp.beats ?? 3)))
    if (pr <= 0) continue
    const rMax = sp.r_km || 1.5, r = rMax * pr, lines = spreadLines(geo, at, sp.area && areas[sp.area], rMax)
    const settled = new Path2D(), front = new Path2D(), fire = sp.kind === 'fire', last = s.dur / s.beat_s
    const out = 1 - k.prog(s.beat, last - 0.6, last) * (sp.keep ? 0 : 1)
    for (const ln of lines) {
      if (ln.d > r) break
      const pa = r - ln.d < rMax * 0.12 ? front : settled
      let pen = false
      for (const pt of ln.pts) { const q = P(pt[0], pt[1]); if (q[2] < 0) { pen = false; continue } if (pen) pa.lineTo(q[0], q[1]); else { pa.moveTo(q[0], q[1]); pen = true } }
    }
    g.save(); g.lineCap = 'round'; g.lineJoin = 'round'; g.globalAlpha *= out
    g.strokeStyle = fire ? 'rgba(120,30,20,0.55)' : k.rgba(sp.color || '#FFD58A', 0.5); g.lineWidth = 4; g.stroke(settled)
    g.strokeStyle = fire ? 'rgba(60,20,15,0.6)' : 'rgba(255,250,238,0.75)'; g.lineWidth = 1.3; g.stroke(settled)
    const fl = fire ? 0.75 + 0.25 * Math.sin(T * 23) : 1
    g.strokeStyle = fire ? `rgba(255,140,50,${0.35 * fl})` : 'rgba(255,236,190,0.35)'; g.lineWidth = 10; g.stroke(front)
    g.strokeStyle = fire ? `rgba(255,220,150,${0.95 * fl})` : 'rgba(255,248,232,0.95)'; g.lineWidth = 2.2; g.stroke(front)
    g.restore()
  }
  // extent morph: the outline of the previous era slides to the next one, with arrows that say whether
  // the city grows or shrinks, and the old outline left behind as a dashed line
  if (p.morph && !p.rings) {
    const A0 = areas[p.morph.from], A1 = areas[p.morph.to], L1 = layers.find((L) => L.area === p.morph.to)
    if (A0 && A1 && A0.ring && A1.ring) {
      const b0 = p.morph.beat ?? 0.3, mp = k.ease.inOut(k.prog(s.beat, b0, b0 + (p.morph.beats ?? 3))), last = s.dur / s.beat_s
      const show = k.prog(s.beat, b0 - 0.4, b0) * (1 - k.prog(s.beat, last - 0.5, last))
      const grows = (A1.km2 || 0) >= (A0.km2 || 0), color = (L1 && L1.color) || '#FFD58A'
      const seed = grows ? A0 : A1, outer = grows ? A1 : A0, maxD = C3.morphField(`${seed.id}>${outer.id}`, seed.ring, outer.ring, R).maxD
      const fr = (grows ? mp : 1 - mp) * maxD * 1.06
      g.save(); g.globalAlpha *= show; g.lineJoin = 'round'
      g.setLineDash([6, 8]); g.strokeStyle = 'rgba(255,255,255,0.55)'; g.lineWidth = 1.4; g.stroke(ringPath(closed(A0.ring))); g.setLineDash([])
      // arrows ride the light's front: each starts at the nearest point of the seed extent and runs
      // straight to a point of the outer outline (growing outwards, shrinking inwards)
      const rays = morphRays(seed, outer)
      rays.forEach((r, ri) => {
        if (ri % 3 || r.d < Math.max(0.15, maxD * 0.2)) return
        const along = Math.min(fr, r.d), am = k.clamp((r.d - along) / 0.12, 0, 1) * k.clamp(along / 0.08, 0, 1) * (mp > 0 && mp < 1 ? 1 : 0)
        if (am <= 0) return
        const sgn = grows ? 1 : -1, a = [r.n[0] + r.ux * along, r.n[1] + r.uy * along], b = [a[0] + sgn * r.ux * 0.12, a[1] + sgn * r.uy * 0.12], qa = P(a[0], a[1]), qb = P(b[0], b[1])
        if (qa[2] < 0 || qb[2] < 0) return
        const dx = qb[0] - qa[0], dy = qb[1] - qa[1], dl = Math.hypot(dx, dy) || 1, ux = dx / dl, uy = dy / dl
        g.save(); g.globalAlpha *= am * 0.95; g.lineCap = 'round'; g.lineJoin = 'round'
        const tx = qa[0] + ux * 16, ty = qa[1] + uy * 16
        const chev = () => { g.beginPath(); g.moveTo(tx - ux * 16 - uy * 11, ty - uy * 16 + ux * 11); g.lineTo(tx, ty); g.lineTo(tx - ux * 16 + uy * 11, ty - uy * 16 - ux * 11); g.stroke() }
        g.strokeStyle = 'rgba(0,0,0,0.45)'; g.lineWidth = 6; chev(); g.strokeStyle = '#FFFFFF'; g.lineWidth = 3; chev()
        g.restore()
      })
      // the word, next to the outline's highest point on screen
      // where the outline moves most, among the points well inside the frame
      let topQ = null, best = 0
      for (const r of rays) { const q = P(r.p[0], r.p[1]); if (q[2] > 0 && q[0] > W * 0.36 && q[0] < W * 0.74 && q[1] > H * 0.3 && q[1] < H * 0.72 && r.d >= best) { best = r.d; topQ = q } }
      const be = b0 + (p.morph.beats ?? 3), la = k.prog(s.beat, b0 + 0.5, b0 + 1.3) * (1 - k.prog(s.beat, be + 1, be + 1.8)) * show
      if (topQ && la > 0) {
        const zh = /^zh/.test(lang), word = grows ? (zh ? '城区扩大' : 'The city grows') : (zh ? '城区收缩' : 'The city shrinks')
        const sub = `${k.labelOf(A0.label, lang)} → ${k.labelOf(A1.label, lang)}`
        g.save(); g.globalAlpha *= la; taken.push(k.callout2(g, topQ[0], topQ[1], word, sub, { size: 32, dot: color })); g.restore()
      }
      g.restore()
    }
  }
  // founding: a column of light on the spot and ripples spreading out over the ground
  if (p.found && !p.rings) {
    const at = byIdAll[p.found.place]
    if (at) {
      const b0 = p.found.beat ?? 0.5, fa = k.prog(s.beat, b0, b0 + 0.5) * (1 - k.prog(s.beat, s.dur / s.beat_s - 0.6, s.dur / s.beat_s))
      const q0 = P(at.x, at.y, 0), q1 = P(at.x, at.y, 0.45)
      if (fa > 0 && q0[2] > 0) {
        g.save(); g.globalAlpha *= fa
        for (let i = 0; i < 3; i++) {
          const ph = ((s.beat - b0) / 2.4 + i / 3) % 1; if (s.beat - b0 < i * 0.8) continue
          const rr2 = 0.05 + 0.55 * k.ease.out(ph), ring = []
          for (let a = 0; a <= 48; a++) ring.push([at.x + Math.cos(a / 48 * Math.PI * 2) * rr2, at.y + Math.sin(a / 48 * Math.PI * 2) * rr2])
          g.strokeStyle = `rgba(255,214,140,${(0.9 * (1 - ph)).toFixed(3)})`; g.lineWidth = 2.2; g.stroke(ringPath(ring))
        }
        const bw = 10, beam = g.createLinearGradient(q0[0], q0[1], q1[0], q1[1])
        beam.addColorStop(0, 'rgba(255,226,170,0.85)'); beam.addColorStop(1, 'rgba(255,226,170,0)')
        g.fillStyle = beam; g.beginPath(); g.moveTo(q0[0] - bw, q0[1]); g.lineTo(q0[0] + bw, q0[1]); g.lineTo(q1[0] + 2, q1[1]); g.lineTo(q1[0] - 2, q1[1]); g.closePath(); g.fill()
        const gl3 = g.createRadialGradient(q0[0], q0[1], 0, q0[0], q0[1], 60); gl3.addColorStop(0, 'rgba(255,226,170,0.7)'); gl3.addColorStop(1, 'rgba(255,226,170,0)')
        g.fillStyle = gl3; g.beginPath(); g.ellipse(q0[0], q0[1], 60, 34, 0, 0, Math.PI * 2); g.fill()
        g.restore()
      }
    }
  }
  // water: the river channel brightens from upstream, then streaks of light run downstream along it
  if (p.river && !p.rings) {
    // `river: { name }` (or chronology.river) picks the river by name and joins its OSM pieces end to
    // end; else the longest river
    const rname = (p.river && p.river.name) || ch.river
    const rv = rname ? riverByName(geo, rname) : (geo.rivers || []).filter((x) => !x.canal).sort((a, b) => b.pts.length - a.pts.length)[0]
    if (rv) {
      const fw = riverOf(rv), last = s.dur / s.beat_s
      const reveal = k.ease.inOut(k.prog(u, 0.02, 0.45)), ra = 1 - k.prog(s.beat, last - 0.6, last) * (p.river.keep ? 0 : 1)
      const nshow = Math.max(2, Math.ceil(rv.pts.length * reveal))
      g.save(); g.globalAlpha *= ra; g.lineCap = 'round'; g.lineJoin = 'round'
      const ch2 = ringPath(rv.pts.slice(0, nshow))
      g.strokeStyle = 'rgba(90,190,230,0.10)'; g.lineWidth = 26; g.stroke(ch2)
      g.strokeStyle = 'rgba(120,205,240,0.16)'; g.lineWidth = 7; g.stroke(ch2)
      const rr = k.rng(strHash(rv.name || 'river')), Lr = fw.L * reveal
      for (let i = 0; i < 900; i++) {
        const s0 = rr() * fw.L, v = 0.22 * (0.75 + 0.5 * rr()), lat = (rr() - 0.5) * 0.06, len = 0.07 + 0.09 * rr(), tw = rr()
        const d = (s0 + T * v) % fw.L
        if (d > Lr) continue
        const [x, y, tx, ty] = fw.at(d), [x2, y2] = fw.at(Math.max(0, d - len))
        const nx = -ty, ny = tx, q0 = P(x + nx * lat, y + ny * lat, 0.002), q1 = P(x2 + nx * lat, y2 + ny * lat, 0.002)
        if (q0[2] < 0 || q1[2] < 0 || q0[0] < -50 || q0[0] > W + 50 || q0[1] < -50 || q0[1] > H + 50) continue
        const gr = g.createLinearGradient(q1[0], q1[1], q0[0], q0[1])
        gr.addColorStop(0, 'rgba(200,240,255,0)'); gr.addColorStop(1, `rgba(235,250,255,${(0.55 + 0.4 * tw).toFixed(2)})`)
        g.strokeStyle = gr; g.lineWidth = 1.4 + 1.4 * tw; g.beginPath(); g.moveTo(q1[0], q1[1]); g.lineTo(q0[0], q0[1]); g.stroke()
      }
      g.restore()
    }
  }
  // fire: a flickering flame front on the scar ring (the shader chars the inside)
  for (const f of p.focus || []) {
    const F = (ch.focus || {})[f.id], at = F && byIdAll[F.place]
    if (!at || F.kind !== 'scar') continue
    const fp = k.ease.out(k.prog(s.beat, f.beat || 0, (f.beat || 0) + 2.5)), last = s.dur / s.beat_s, fa = k.prog(s.beat, f.beat || 0, (f.beat || 0) + 0.6) * (1 - k.prog(s.beat, last - 0.8, last))
    const r = (F.ring_km || 0.6) * fp, rr = k.rng(17)
    g.save()
    for (let i = 0; i < 120; i++) {
      const a = rr() * Math.PI * 2, jitter = 0.86 + 0.22 * rr(), x = at.x + Math.cos(a) * r * jitter, y = at.y + Math.sin(a) * r * jitter
      const hgt = 0.01 + 0.03 * rr() * (0.6 + 0.4 * Math.sin(T * 9 + i)), q0 = P(x, y, 0), q1 = P(x, y, hgt)
      if (q0[2] < 0) continue
      const gr = g.createLinearGradient(q0[0], q0[1], q1[0], q1[1]); gr.addColorStop(0, `rgba(255,150,60,${0.85 * fa})`); gr.addColorStop(1, 'rgba(255,230,160,0)')
      g.strokeStyle = gr; g.lineWidth = 2 + 3 * rr(); g.beginPath(); g.moveTo(q0[0], q0[1]); g.lineTo(q1[0] + Math.sin(T * 6 + i) * 3, q1[1]); g.stroke()
    }
    g.restore()
  }
  // axes: a beam drawn from a hub to each end, a pulse running along it, sun-like seals at the ends
  const seal = (q, rad, a, color) => {
    g.save(); g.globalAlpha *= a; g.translate(q[0], q[1]); g.scale(1, 0.62)
    const gl2 = g.createRadialGradient(0, 0, 0, 0, 0, rad * 1.6); gl2.addColorStop(0, k.rgba(color, 0.55)); gl2.addColorStop(1, k.rgba(color, 0))
    g.fillStyle = gl2; g.beginPath(); g.arc(0, 0, rad * 1.6, 0, Math.PI * 2); g.fill()
    g.strokeStyle = k.rgba(color, 0.95); g.lineWidth = 2; g.beginPath(); g.arc(0, 0, rad, 0, Math.PI * 2); g.stroke()
    g.lineWidth = 1.2; g.beginPath(); g.arc(0, 0, rad * 0.62, 0, Math.PI * 2); g.stroke()
    g.rotate(T * 0.6); for (let i = 0; i < 12; i++) { g.rotate(Math.PI / 6); g.beginPath(); g.moveTo(rad * 0.66, 0); g.quadraticCurveTo(rad * 0.85, rad * 0.12, rad * 0.98, 0); g.stroke() }
    g.restore()
  }
  for (const ax of p.axis || []) {
    const A = (ch.axes || {})[ax.id]; if (!A) continue
    const hub = byIdAll[A.from]; if (!hub) continue
    const b0 = ax.beat || 0, last = s.dur / s.beat_s, out = 1 - k.prog(s.beat, last - 0.6, last)
    const color = A.color || '#FFC86E', qh = P(hub.x, hub.y, 0.003)
    seal(qh, 34, k.prog(s.beat, b0, b0 + 0.6) * out, color)
    A.to.forEach((tid, n) => {
      const to = byIdAll[tid]; if (!to) return
      const dp = k.ease.inOut(k.prog(s.beat, b0 + 0.4 + n * 0.5, b0 + 2 + n * 0.5))
      if (dp <= 0) return
      const steps = 40, pts = []
      for (let i = 0; i <= steps * dp; i++) { const t2 = i / steps; pts.push([hub.x + (to.x - hub.x) * t2, hub.y + (to.y - hub.y) * t2]) }
      const pa = ringPath(pts)
      g.save(); g.globalAlpha *= out; g.lineCap = 'round'
      g.strokeStyle = k.rgba(color, 0.25); g.lineWidth = 12; g.stroke(pa)
      g.strokeStyle = k.rgba(color, 0.95); g.lineWidth = 3; g.stroke(pa)
      g.strokeStyle = 'rgba(255,255,255,0.9)'; g.lineWidth = 1; g.stroke(pa)
      const pt = (T * 0.35 + n * 0.3) % 1, pq = P(hub.x + (to.x - hub.x) * pt * dp, hub.y + (to.y - hub.y) * pt * dp, 0.003)
      if (pq[2] > 0) { g.fillStyle = '#FFF4DC'; g.beginPath(); g.arc(pq[0], pq[1], 4, 0, Math.PI * 2); g.fill() }
      g.restore()
      if (dp >= 1) seal(P(to.x, to.y, 0.003), 22, k.prog(s.beat, b0 + 2 + n * 0.5, b0 + 2.6 + n * 0.5) * out, color)
    })
    const la = k.prog(s.beat, b0 + 1.2, b0 + 2) * out
    if (la > 0 && qh[2] > 0) { g.save(); g.globalAlpha *= la; k.callout2(g, qh[0], qh[1], k.labelOf(A.title, lang), k.labelOf(A.sub, lang) || '', { size: 24, dot: color, dx: 40, dy: -50 }); g.restore() }
  }
  // emblems: a rendered object floating over its place (a seal, a coin, an inscription), with a beam of light
  const emblemDraw = (q, size, F, a) => {
    g.save(); g.globalAlpha *= a
    const bob = Math.sin(T * 1.6) * 6, cx = q[0], cy = q[1] - 150 + bob
    const beam = g.createLinearGradient(cx, cy, cx, q[1]); beam.addColorStop(0, 'rgba(255,214,140,0.0)'); beam.addColorStop(1, 'rgba(255,214,140,0.55)')
    g.fillStyle = beam; g.beginPath(); g.moveTo(cx - 3, cy + size * 0.6); g.lineTo(cx + 3, cy + size * 0.6); g.lineTo(cx + 18, q[1]); g.lineTo(cx - 18, q[1]); g.closePath(); g.fill()
    g.fillStyle = 'rgba(255,214,140,0.35)'; g.beginPath(); g.ellipse(q[0], q[1], 46, 16, 0, 0, Math.PI * 2); g.fill()
    const halo2 = g.createRadialGradient(cx, cy, size * 0.3, cx, cy, size * 1.4); halo2.addColorStop(0, 'rgba(255,220,150,0.45)'); halo2.addColorStop(1, 'rgba(255,220,150,0)')
    g.fillStyle = halo2; g.beginPath(); g.arc(cx, cy, size * 1.4, 0, Math.PI * 2); g.fill()
    // medallion with a slow turn (scaleX) for depth
    g.translate(cx, cy); g.scale(0.82 + 0.18 * Math.cos(T * 0.9), 1)
    const face = g.createRadialGradient(-size * 0.3, -size * 0.3, size * 0.1, 0, 0, size)
    face.addColorStop(0, '#FFF0C8'); face.addColorStop(0.6, '#E2B86A'); face.addColorStop(1, '#9C7330')
    g.fillStyle = face; g.beginPath(); g.arc(0, 0, size, 0, Math.PI * 2); g.fill()
    g.strokeStyle = '#7A5622'; g.lineWidth = 2; g.beginPath(); g.arc(0, 0, size * 0.86, 0, Math.PI * 2); g.stroke()
    // laurel
    g.strokeStyle = '#6E4E1E'; g.lineWidth = 1.6
    for (const side of [-1, 1]) for (let i = 0; i < 9; i++) { const a = Math.PI * (0.62 + i * 0.085) * side + (side < 0 ? 0 : 0), r0 = size * 0.74; const x = Math.cos(Math.PI / 2 + side * (0.4 + i * 0.27)) * r0, y = Math.sin(Math.PI / 2 + side * (0.4 + i * 0.27)) * r0; g.beginPath(); g.ellipse(x, y, size * 0.11, size * 0.045, Math.atan2(y, x) + side * 0.9, 0, Math.PI * 2); g.stroke(); void a }
    g.fillStyle = '#5A3E14'; g.font = `700 ${Math.round(size * 0.42)}px ${k.FONT.serif || 'Georgia, serif'}`; g.textAlign = 'center'; g.textBaseline = 'middle'
    g.fillText(F.glyph || '', 0, 2)
    g.restore()
    return [cx, cy]
  }
  const free = (r) => !taken.some((t) => r[0] < t[0] + t[2] + 8 && r[0] + r[2] + 8 > t[0] && r[1] < t[1] + t[3] + 6 && r[1] + r[3] + 6 > t[1])
  const onScreen = (q) => q[2] > 0 && q[0] > W * 0.3 && q[0] < W * 0.94 && q[1] > H * 0.1 && q[1] < H * 0.8
  // rings named on the closing view
  if (p.rings) {
    const used = []
    for (const L of layers) {
      const A = areas[L.area]; if (!A || !A.ring || L.spot) continue
      const topPt = A.ring.reduce((m, q) => (q[1] > m[1] ? q : m), A.ring[0]), q = P(topPt[0], topPt[1])
      if (q[2] < 0) continue
      g.save(); g.globalAlpha *= k.prog(s.beat, 0.8, 2.5); g.font = `400 18px ${k.FONT.sans}`; g.fillStyle = 'rgba(255,255,255,0.88)'; g.textAlign = 'center'; g.textBaseline = 'bottom'
      const label = `${k.labelOf(A.label, lang)} · ${k.yearText(L.from, lang)}`, lw = g.measureText(label).width
      let ly = q[1] - 8
      while (used.some((r) => Math.abs(r[0] - q[0]) < (r[2] + lw) / 2 + 10 && Math.abs(r[1] - ly) < 24)) ly -= 24
      used.push([q[0], ly, lw]); g.fillText(label, q[0], ly); g.restore()
    }
  }
  if (p.era_label && !p.clean) {
    const L = layers.find((x, i) => eraA[i] > 0.5 && !x.spot), A = L && areas[L.area]
    if (A) {
      const topPt = A.ring.reduce((m, q) => (q[1] > m[1] ? q : m), A.ring[0]), q = P(A.x, topPt[1])
      if (q[2] > 0) { g.save(); g.globalAlpha *= k.prog(s.beat, 0.5, 1.5); taken.push(k.callout2(g, q[0], q[1], k.labelOf(A.label, lang), '', { size: 22, dot: L.color })); g.restore() }
    }
  }
  const focused = new Set()
  for (const f of p.focus || []) {
    const F = (ch.focus || {})[f.id], at = F && byId[F.place]
    if (!at) continue
    focused.add(F.place)
    const q = P(at.x, at.y, 0.02), last = s.dur / s.beat_s
    const a = k.prog(s.beat, (f.beat || 0) + 0.5, (f.beat || 0) + 1.2) * (1 - k.prog(s.beat, last - 0.5, last))
    if (q[2] < 0 || a <= 0) continue
    if (F.kind === 'scar') {
      const rr = k.rng(41), r = (F.ring_km || 0.6) * W / (2 * view.d * Math.tan(((view.fov || 34) * Math.PI) / 360)) * 0.9
      for (let i = 0; i < 50; i++) { const a0 = rr() * Math.PI * 2, d = Math.sqrt(rr()) * r, x = q[0] + Math.cos(a0) * d, y = q[1] + Math.sin(a0) * d * 0.55 - ((s.t * (30 + rr() * 60) + rr() * 80) % 90); g.fillStyle = `rgba(255,${130 + Math.round(rr() * 80)},70,${(0.3 + 0.4 * rr()).toFixed(2) * a})`; g.beginPath(); g.arc(x, y, 1.4 + rr() * 2, 0, Math.PI * 2); g.fill() }
    }
    if (F.kind === 'emblem') { const c2 = emblemDraw(q, 54, F, a); g.save(); g.globalAlpha *= a; taken.push(k.callout2(g, c2[0] + 62, c2[1], k.labelOf(F.title, lang), k.labelOf(F.sub, lang) || '', { size: 24, dot: '#FFD58A' })); g.restore(); continue }
    const builtSub = at.built != null && F.kind !== 'scar' && F.show_built !== false ? (/^zh/.test(lang) ? `建于 ${k.yearText(at.built, lang)} 年 · Wikidata` : `built ${k.yearText(at.built, lang)} · Wikidata`) : ''
    g.save(); g.globalAlpha *= a; taken.push(k.callout2(g, q[0], q[1], k.labelOf(F.title, lang), k.labelOf(F.sub, lang) || builtSub, { size: 24, dot: F.kind === 'scar' ? '#FF6A4D' : '#FFD58A', leader: [q[0], q[1] + 40] })); g.restore()
  }
  let line = null, note = null, person = null
  for (const ev of ch.events || []) {
    const vis = win(ev.year, ev.until ?? ev.year + 40, ev.fade ?? 10)
    if (vis <= 0) continue
    if (ev.kind === 'person') { if (vis > (person?.vis ?? 0)) person = { ev, vis }; continue }
    if (vis > 0.5) { line = k.labelOf(ev.title, lang); note = ev.sub ? k.labelOf(ev.sub, lang) : null }
    const at = ev.place && byId[ev.place]
    if (!at || focused.has(ev.place) || p.clean || p.heights) continue
    const q = P(at.x, at.y, 0.02)
    if (!onScreen(q)) continue
    g.save(); g.globalAlpha *= vis
    const r0 = [q[0] + 14, q[1] - 40, 300, 48]
    if (free(r0)) taken.push(k.callout2(g, q[0], q[1], k.labelOf(ev.title, lang), ev.sub ? k.labelOf(ev.sub, lang) : '', { size: 22, dot: ev.kind === 'scar' ? '#FF6A4D' : '#FFFFFF' }))
    g.restore()
  }
  if (!p.clean) for (const q0 of ch.places || []) {
    if (p.heights && !q0.modern) continue
    const vis = win(q0.from, q0.to ?? null, q0.fade ?? 25), at = byId[q0.id]
    if (!at || vis <= 0 || focused.has(q0.id)) continue
    const q = P(at.x, at.y, 0.02)
    if (!onScreen(q)) continue
    g.save(); g.font = `500 19px ${k.FONT.sans}`
    const w = g.measureText(k.labelOf(at.label, lang)).width
    const fresh = q0.mark_built ? k.clamp((year - q0.from) / 20, 0, 1) : 1
    const sub2 = q0.mark_built && fresh < 1 ? (/^zh/.test(lang) ? '新建' : 'new') : ''
    if (q0.mark_built && fresh < 1) { const rg = 14 + 50 * fresh; g.save(); g.globalAlpha *= (1 - fresh) * vis; g.strokeStyle = '#FFD58A'; g.lineWidth = 2; g.beginPath(); g.ellipse(q[0], q[1], rg, rg * 0.55, 0, 0, Math.PI * 2); g.stroke(); g.restore() }
    if (free([q[0] + 16, q[1] - 32, w + 18, 30])) { g.globalAlpha *= vis * 0.9; taken.push(k.callout2(g, q[0], q[1], k.labelOf(at.label, lang), sub2, { size: 19, dot: q0.mark_built && fresh < 1 ? '#FFD58A' : '#FFFFFF' })) }
    g.restore()
  }
  // heights: measure the tallest mapped building in view
  if (p.heights) {
    const st = gl.state, a = p.tint ? lerp(p.tint) : 1
    let best = -1, bh = 0
    for (let i = 0; i < geo.buildings.length; i++) {
      if (st.heights.est[i]) continue
      const c = st.heights.centroids[i], q = P(c[0], c[1])
      if (!onScreen(q)) continue
      if (st.heights.h[i] > bh) { bh = st.heights.h[i]; best = i }
    }
    if (best >= 0) {
      const c = st.heights.centroids[best], z = bh / 1000 * st.exaggerate * grow, q0 = P(c[0], c[1], 0), q1 = P(c[0], c[1], z)
      g.save(); g.globalAlpha *= a; g.strokeStyle = 'rgba(255,255,255,0.9)'; g.lineWidth = 1.5
      g.beginPath(); g.moveTo(q0[0] + 18, q0[1]); g.lineTo(q1[0] + 18, q1[1]); g.stroke()
      for (let t = 0; t <= 5; t++) { const y = q0[1] + (q1[1] - q0[1]) * t / 5; g.beginPath(); g.moveTo(q0[0] + 14, y); g.lineTo(q0[0] + 22, y); g.stroke() }
      g.restore()
      // say what is measured: the landmark's name when the tallest building is one, and the source
      const zh = /^zh/.test(lang), pl = (geo.places || []).find((x) => x.footprint === best)
      const name = pl ? k.labelOf(pl.label, lang) : zh ? '视野内最高的建筑' : 'Tallest building in view'
      const src = pl && pl.qid ? 'Wikidata' : 'OpenStreetMap'
      const sub = `${Math.round(bh)} m · ${pl ? (zh ? '视野内最高 · ' : 'tallest in view · ') : ''}${src}`
      g.save(); g.globalAlpha *= a; taken.push(k.callout2(g, q1[0] + 18, q1[1], name, sub, { size: 24, dot: '#FFFFFF', dx: 30, dy: -30 })); g.restore()
    }
    g.save(); g.globalAlpha *= a
    const x = W * 0.035, y = H * 0.66, w = 220, gr = g.createLinearGradient(x, 0, x + w, 0)
    for (const [t, c] of [[0, '#8FB3E8'], [0.4, '#CCBDEB'], [0.7, '#F5C7D6'], [1, '#FFF7EE']]) gr.addColorStop(t, c)
    g.fillStyle = gr; g.fillRect(x, y, w, 5)
    g.fillStyle = 'rgba(243,241,236,0.65)'; g.font = `13px ${k.FONT.mono || 'monospace'}`; g.textBaseline = 'top'; g.textAlign = 'left'; g.fillText('0 m', x, y + 11); g.textAlign = 'right'; g.fillText('100 m', x + w, y + 11)
    g.textAlign = 'left'; g.fillText(k.labelOf(ch.heights_note || { en: 'heights: OpenStreetMap where mapped, else local median' }, lang), x, y + 30)
    // how much of that is measured: the share of buildings with a mapped height
    if (geo.heights_share != null) g.fillText(/^zh/.test(lang) ? `已标注高度的建筑：${Math.round(geo.heights_share * 100)}%` : `buildings with a mapped height: ${Math.round(geo.heights_share * 100)}%`, x, y + 50)
    g.restore()
  }
  g.restore()
  // ---- left block, HUD, shades ----
  shades()
  k.hud(g, s, ch.hud || [], 0.85)
  const eraName = (ch.eras || []).reduce((m, x) => (year >= x.from ? x : m), null)
  if (!p.rings && !p.clean) {
    const big = p.big ? { big: k.labelOf(p.big.text, lang), unit: p.big.unit ? k.labelOf(p.big.unit, lang) : null, line: p.big.line ? k.labelOf(p.big.line, lang) : null, note: p.big.note ? k.labelOf(p.big.note, lang) : null }
      : { big: k.yearText(year, lang), line, note }
    const litL = layers.reduce((m, L, i) => (!L.spot && eraA[i] > 0.5 && (!m || L.from > m.from) ? L : m), null)
    k.dataBlock(g, s, { code: eraName ? eraName.code : '', era: eraName ? k.labelOf(eraName.label, lang) : '', color: litL ? litL.color : null, ...big }, cityA)
  }
  if (person && !p.rings && !p.big && !p.clean) {
    const ev = person.ev
    g.save(); g.globalAlpha = person.vis * cityA
    const x = W * 0.035, y = H * 0.6
    g.fillStyle = 'rgba(243,241,236,0.85)'; g.fillRect(x, y, 2, 46)
    g.fillStyle = '#F3F1EC'; g.font = `500 24px ${k.FONT.sans}`; g.textAlign = 'left'; g.textBaseline = 'top'; g.fillText(k.labelOf(ev.title, lang), x + 14, y)
    if (ev.sub) { g.fillStyle = '#A9A7A1'; g.font = `400 17px ${k.FONT.sans}`; g.fillText(k.labelOf(ev.sub, lang), x + 14, y + 30) }
    g.restore()
  }
})
