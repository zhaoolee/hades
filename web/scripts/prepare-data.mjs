import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
const source = resolve(import.meta.dirname, '../../generated/all.json')
const output = resolve(import.meta.dirname, '../public/data/dialogues.json')
const raw = JSON.parse(await readFile(source, 'utf8'))
const records = raw.filter(x => x.en && x.zh).map(({ id, channel, speaker, en, zh }) => ({ id, channel, speaker, en, zh }))
const body = JSON.stringify({ schemaVersion: 1, count: records.length, hash: createHash('sha256').update(JSON.stringify(records)).digest('hex').slice(0, 12), records })
await mkdir(dirname(output), { recursive: true }); await writeFile(output, body)
console.log(`Prepared ${records.length} dialogues (${(body.length / 1024 / 1024).toFixed(2)} MiB)`)
