// Screenshot each map view in output/<city>/map/preview.html at 1920x1080.
// Usage: node scripts/shoot_preview.mjs output/pune/map
import { chromium } from 'playwright'
import { resolve, join } from 'node:path'
import { pathToFileURL } from 'node:url'

const dir = resolve(process.argv[2])
const browser = await chromium.launch({ channel: process.env.RECORD_CHANNEL || undefined })
const page = await browser.newPage({ viewport: { width: 1968, height: 1200 } })
const errors = []
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
await page.goto(pathToFileURL(join(dir, 'preview.html')).href)
for (const id of await page.$$eval('section', s => s.map(x => x.id))) {
  await page.locator(`#${id} svg`).screenshot({ path: join(dir, `preview_${id}.png`) })
  console.log(`preview_${id}.png`)
}
console.log(`console errors: ${errors.length}`)
await browser.close()
