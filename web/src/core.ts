import type { Dialogue, DiffPart, Session } from './types'

export function normalizeAnswer(value: string): string {
  return value.normalize('NFKC').toLowerCase()
    .replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/[–—]/g, '-')
    .replace(/^[\s"'“”‘’.,!?;:()\[\]{}…-]+|[\s"'“”‘’.,!?;:()\[\]{}…-]+$/g, '')
    .replace(/[.,!?;:"()[\]{}…-]+/g, ' ').replace(/\s+/g, ' ').trim()
}

export function compareAnswer(input: string, expected: string) {
  const a = normalizeAnswer(input).split(' ').filter(Boolean)
  const b = normalizeAnswer(expected).split(' ').filter(Boolean)
  const dp = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--)
    dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
  const parts: DiffPart[] = []; let i = 0; let j = 0
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) { parts.push({ text: b[j], kind: 'same' }); i++; j++ }
    else if (j < b.length && (i === a.length || dp[i][j + 1] >= dp[i + 1]?.[j])) { parts.push({ text: b[j], kind: 'missing' }); j++ }
    else { parts.push({ text: a[i], kind: 'extra' }); i++ }
  }
  return { correct: a.length > 0 && a.join(' ') === b.join(' '), parts }
}

export function filterDialogues(lines: Dialogue[], filter: { channel: string; query: string }) {
  const q = filter.query.toLocaleLowerCase().trim()
  return lines.filter((line) => (filter.channel === 'all' || line.channel === filter.channel) &&
    (!q || `${line.id} ${line.channel} ${line.speaker} ${line.en} ${line.zh}`.toLocaleLowerCase().includes(q)))
}
export const nextIndex = (current: number, delta: number, length: number) => length ? (current + delta + length) % length : 0
export const createSession = (): Session => ({ completed: 0, correct: 0, reviewIds: [] })
export function updateProgress(session: Session, id: string, correct: boolean): Session {
  return { ...session, completed: session.completed + 1, correct: session.correct + Number(correct),
    reviewIds: correct ? session.reviewIds.filter((x) => x !== id) : Array.from(new Set([...session.reviewIds, id])), lastId: id }
}
