#!/usr/bin/env node
// Runs the chronicle-ink geo.mjs unchanged, but records every map read (Wikidata, Nominatim, Overpass)
// to <project>/geo/cache/ on the first run and replays it afterwards. Overpass is blocked on the home
// network, so the first run happens once on another network and later reruns work offline.
//
//   node tools/geo_cached.mjs --project <dir> [--offline]
//
// --offline fails on any read that is not cached instead of going to the network.
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const SKILL = resolve(import.meta.dirname, '../vendor/chronicle-ink-0.4.3/chronicle-ink')
const arg = (k) => { const i = process.argv.indexOf(`--${k}`); return i < 0 ? null : process.argv[i + 1] }
const project = arg('project')
if (!project) { console.error('Usage: node tools/geo_cached.mjs --project <dir> [--offline]'); process.exit(2) }
const offline = process.argv.includes('--offline')
const cacheDir = join(resolve(project), 'geo', 'cache')
mkdirSync(cacheDir, { recursive: true })

const MAP_HOSTS = /(^|\.)(wikidata\.org|openstreetmap\.org|overpass-api\.de|overpass\.kumi\.systems)$/
const realFetch = globalThis.fetch
let hits = 0, misses = 0

globalThis.fetch = async (input, init = {}) => {
  const url = typeof input === 'string' ? input : input.url
  if (!MAP_HOSTS.test(new URL(url).hostname)) return realFetch(input, init)
  const body = typeof init.body === 'string' ? init.body : init.body ? String(init.body) : ''
  const key = createHash('sha256').update(`${init.method ?? 'GET'} ${url}\n${body}`).digest('hex').slice(0, 32)
  const file = join(cacheDir, `${key}.json`)
  if (existsSync(file)) {
    hits++
    const rec = JSON.parse(readFileSync(file, 'utf8'))
    return new Response(rec.body, { status: rec.status, headers: { 'content-type': rec.type } })
  }
  if (offline) throw new Error(`geo cache miss (offline): ${url}`)
  misses++
  const res = await realFetch(input, init)
  const text = await res.text()
  if (res.ok) writeFileSync(file, JSON.stringify({ url, request_body: body, status: res.status, type: res.headers.get('content-type') ?? 'application/json', at: new Date().toISOString(), body: text }))
  return new Response(text, { status: res.status, headers: { 'content-type': res.headers.get('content-type') ?? 'application/json' } })
}

process.on('exit', () => console.error(`[geo_cached] ${hits} cached, ${misses} fetched → ${cacheDir}`))
await import(pathToFileURL(join(SKILL, 'scripts', 'geo.mjs')).href)
