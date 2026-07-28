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
  afterEach(cleanup)
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
})
