import { describe, expect, it } from 'vitest'
import { compareAnswer, createSession, filterDialogues, nextIndex, normalizeAnswer, updateProgress } from './core'
import type { Dialogue } from './types'

const lines: Dialogue[] = [
  { id: 'Achilles_1', channel: 'Achilles', speaker: 'Achilles', en: "I'll be there.", zh: '我会去。' },
  { id: 'Hades_1', channel: 'Hades', speaker: 'Hades', en: 'There is no escape!', zh: '无处可逃！' },
]

describe('dictation normalization', () => {
  it('ignores case, outer punctuation, curly apostrophes and repeated whitespace', () => {
    expect(normalizeAnswer(' “I’ll   BE there!” ')).toBe("i'll be there")
  })
  it('keeps apostrophes because contractions change meaning', () => {
    expect(normalizeAnswer("well")).not.toBe(normalizeAnswer("we'll"))
  })
  it('returns word-level feedback for missing and extra words', () => {
    const result = compareAnswer('There no escape', 'There is no escape!')
    expect(result.correct).toBe(false)
    expect(result.parts.some((part) => part.kind === 'missing' && part.text === 'is')).toBe(true)
  })
})

describe('learning flow', () => {
  it('filters by channel and bilingual search text', () => {
    expect(filterDialogues(lines, { channel: 'Hades', query: '' })).toEqual([lines[1]])
    expect(filterDialogues(lines, { channel: 'all', query: '无处' })).toEqual([lines[1]])
  })
  it('wraps navigation at both ends', () => {
    expect(nextIndex(1, 1, 2)).toBe(0)
    expect(nextIndex(0, -1, 2)).toBe(1)
  })
  it('tracks attempts, correct answers, misses and review IDs', () => {
    const progress = updateProgress(createSession(), 'Hades_1', false)
    expect(progress.completed).toBe(1)
    expect(progress.correct).toBe(0)
    expect(progress.reviewIds).toContain('Hades_1')
    expect(updateProgress(progress, 'Hades_1', true).correct).toBe(1)
  })
})
