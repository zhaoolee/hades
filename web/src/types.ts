export type Dialogue = { id: string; channel: string; speaker: string; en: string; zh: string; audio?: string; portrait?: string }
export type DiffPart = { text: string; kind: 'same' | 'missing' | 'extra' }
export type Session = { completed: number; correct: number; reviewIds: string[]; lastId?: string }
