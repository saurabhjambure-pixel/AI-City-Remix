// Contest cover: one film frame with the film title, 1920x1080 JPEG (ffmpeg here has no drawtext).
//   node scripts/cover.mjs <frame.png> <title> <out.jpg>
import { readFileSync } from 'node:fs'
import { chromium } from 'playwright'

const [frame, title, out] = process.argv.slice(2)
if (!frame || !title || !out) { console.error('usage: node scripts/cover.mjs <frame.png> <title> <out.jpg>'); process.exit(2) }
const img = `data:image/png;base64,${readFileSync(frame).toString('base64')}`
const esc = (t) => t.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#08080a}
  .f{position:absolute;inset:0;background:url(${img}) center/cover no-repeat}
  .g{position:absolute;left:0;right:0;bottom:0;height:46%;background:linear-gradient(180deg,rgba(8,8,10,0) 0%,rgba(8,8,10,.82) 70%)}
  h1{position:absolute;left:96px;right:96px;bottom:110px;margin:0;color:#f3f1ec;
     font:600 112px/1.04 Georgia,'Times New Roman',serif;letter-spacing:.5px;text-shadow:0 4px 24px rgba(0,0,0,.6)}
</style></head><body><div class="f"></div><div class="g"></div><h1>${esc(title)}</h1></body></html>`
const browser = await chromium.launch({ channel: process.env.RECORD_CHANNEL || undefined })
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
await page.setContent(html, { waitUntil: 'load' })
await page.screenshot({ path: out, type: 'jpeg', quality: 90 })
await browser.close()
console.log(`[cover] ${out}`)
