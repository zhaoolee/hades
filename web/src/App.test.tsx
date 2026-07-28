import { cleanup, render, screen, waitFor } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const data = {
  count: 2,
  records: [
    { id: 'Achilles_1', channel: 'Achilles', speaker: 'Achilles', en: "I'll be there.", zh: '我会去。' },
    { id: 'Hades_1', channel: 'Hades', speaker: 'Hades', en: 'There is no escape!', zh: '无处可逃！' },
  ],
}

describe('Hades Listener', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => data }))
  })

  it('loads dialogues and switches between browse and dictation', async () => {
    render(<App />)
    expect(await screen.findByText("I'll be there.")).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: '听写模式' }))
    expect(screen.queryByText("I'll be there.")).toBeNull()
    expect(screen.getByLabelText('输入你听到的英文台词')).toBeTruthy()
  })

  it('shows answer feedback and updates statistics', async () => {
    render(<App />)
    await screen.findByText("I'll be there.")
    await userEvent.click(screen.getByRole('button', { name: '听写模式' }))
    await userEvent.type(screen.getByLabelText('输入你听到的英文台词'), "I'll be there")
    await userEvent.click(screen.getByRole('button', { name: '提交答案' }))
    expect(await screen.findByText(/完全正确/)).toBeTruthy()
    await waitFor(() => expect(screen.getByText('正确').previousElementSibling?.textContent).toBe('1'))
  })

  it('plays locally extracted original audio when the dialogue has an audio path', async () => {
    const play = vi.fn().mockResolvedValue(undefined)
    const pause = vi.fn()
    class FakeAudio {
      src: string
      playbackRate = 1
      currentTime = 0
      onerror: (() => void) | null = null
      constructor(src: string) { this.src = src }
      play = play
      pause = pause
    }
    vi.stubGlobal('Audio', FakeAudio)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...data, records: [{ ...data.records[0], audio: 'audio/Achilles_1.ogg', portrait: 'portraits/Achilles.webp' }] }),
    }))

    render(<App />)
    await screen.findByText("I'll be there.")
    await userEvent.click(screen.getByRole('button', { name: '播放英文台词' }))

    expect(play).toHaveBeenCalledOnce()
    expect(screen.getByText('游戏原声 · 本地提取')).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Achilles 人物立绘' }).getAttribute('src')).toContain('portraits/Achilles.webp')
  })

  it('falls back to browser speech and keeps the notice when original audio fails', async () => {
    const speak = vi.fn()
    vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), getVoices: () => [], speak })
    vi.stubGlobal('SpeechSynthesisUtterance', class { lang = ''; rate = 1; voice = null; constructor(public text: string) {} })
    vi.stubGlobal('Audio', class {
      playbackRate = 1; currentTime = 0; onerror: (() => void) | null = null
      play = () => Promise.reject(new Error('missing'))
      pause = vi.fn()
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...data, records: [{ ...data.records[0], audio: 'audio/missing.ogg' }] }),
    }))

    render(<App />)
    await screen.findByText("I'll be there.")
    await userEvent.click(screen.getByRole('button', { name: '播放英文台词' }))

    await waitFor(() => expect(speak).toHaveBeenCalledOnce())
    expect(screen.getByText('原声加载失败，已改用浏览器语音。')).toBeTruthy()
  })

  it('does not start fallback speech after unmounting during pending playback', async () => {
    let rejectPlay!: (error: Error) => void
    const speak = vi.fn()
    const pause = vi.fn()
    vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), getVoices: () => [], speak })
    vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(public text: string) {} })
    vi.stubGlobal('Audio', class {
      playbackRate = 1; currentTime = 0; onerror: (() => void) | null = null
      play = () => new Promise<void>((_, reject) => { rejectPlay = reject })
      pause = pause
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...data, records: [{ ...data.records[0], audio: 'audio/pending.ogg' }] }),
    }))

    const view = render(<App />)
    await screen.findByText("I'll be there.")
    await userEvent.click(screen.getByRole('button', { name: '播放英文台词' }))
    view.unmount()
    rejectPlay(new Error('aborted'))
    await Promise.resolve()

    expect(pause).toHaveBeenCalledOnce()
    expect(speak).not.toHaveBeenCalled()
  })
})
