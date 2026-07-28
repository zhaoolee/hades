import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
const source = resolve(import.meta.dirname, '../../generated/all.json')
const output = resolve(import.meta.dirname, '../public/data/dialogues.json')
const raw = JSON.parse(await readFile(source, 'utf8'))
let audio = null
try { audio = JSON.parse(await readFile(resolve(import.meta.dirname, '../public/audio/manifest.json'), 'utf8')) } catch {}
const audioIds = new Set(audio?.ids || [])
const extension = audio?.extension
let portraits = null
try { portraits = JSON.parse(await readFile(resolve(import.meta.dirname, '../public/portraits/manifest.json'), 'utf8')) } catch {}
const portraitMap = portraits?.schemaVersion === 1 && portraits?.portraits && typeof portraits.portraits === 'object'
  ? portraits.portraits : {}
const records = raw.filter(x => x.en && x.zh).map(({ id, channel, speaker, en, zh }) => ({
  id, channel, speaker, en, zh,
  ...(extension && audioIds.has(id) ? { audio: `audio/${id}.${extension}` } : {}),
  ...(typeof portraitMap[channel] === 'string' ? { portrait: `portraits/${portraitMap[channel]}` } : {}),
}))
const body = JSON.stringify({ schemaVersion: 1, count: records.length, hash: createHash('sha256').update(JSON.stringify(records)).digest('hex').slice(0, 12), records })
await mkdir(dirname(output), { recursive: true }); await writeFile(output, body)
console.log(`Prepared ${records.length} dialogues (${(body.length / 1024 / 1024).toFixed(2)} MiB)`)
