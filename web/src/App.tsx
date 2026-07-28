import { useEffect, useMemo, useRef, useState } from 'preact/hooks'
import { compareAnswer, createSession, filterDialogues, nextIndex, updateProgress } from './core'
import type { Dialogue, Session } from './types'

type Mode = 'browse' | 'dictation'
type Data = { count: number; records: Dialogue[] }
const STORE = 'hades-listener:v1'
function loadState(): { mode: Mode; channel: string; session: Session; lastId?: string; rate: number } {
  try { return { mode: 'browse', channel: 'all', session: createSession(), rate: .85, ...JSON.parse(localStorage.getItem(STORE) || '{}') } }
  catch { return { mode: 'browse', channel: 'all', session: createSession(), rate: .85 } }
}

export default function App() {
  const initial = useRef(loadState()).current
  const [data, setData] = useState<Data | null>(null); const [error, setError] = useState('')
  const [mode, setMode] = useState<Mode>(initial.mode); const [channel, setChannel] = useState(initial.channel)
  const [query, setQuery] = useState(''); const [index, setIndex] = useState(0); const [answer, setAnswer] = useState('')
  const [result, setResult] = useState<ReturnType<typeof compareAnswer> | null>(null)
  const [session, setSession] = useState<Session>(initial.session); const [rate, setRate] = useState(initial.rate)
  const [ttsError, setTtsError] = useState(''); const [revealed, setRevealed] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const mountedRef = useRef(true)
  const fetchData = () => { setError(''); fetch(`${import.meta.env.BASE_URL}data/dialogues.json`).then(r => { if (!r.ok) throw Error(String(r.status)); return r.json() }).then(setData).catch(() => setError('台词数据加载失败，请检查网络后重试。')) }
  useEffect(fetchData, [])
  const channels = useMemo(() => data ? [...new Set(data.records.map(x => x.channel))].sort() : [], [data])
  const filtered = useMemo(() => data ? filterDialogues(data.records, { channel, query }) : [], [data, channel, query])
  const line = filtered[index]
  useEffect(() => { setIndex(0); resetQuestion() }, [channel, query])
  useEffect(() => { try { localStorage.setItem(STORE, JSON.stringify({ mode, channel, session, lastId: line?.id, rate })) } catch {} }, [mode, channel, session, line?.id, rate])
  useEffect(() => () => { mountedRef.current = false; stopAudio(); window.speechSynthesis?.cancel() }, [])
  const stopAudio = () => { const audio = audioRef.current; audioRef.current = null; if (audio) { audio.onerror = null; audio.pause() } }
  const resetQuestion = () => { setAnswer(''); setResult(null); setRevealed(false); stopAudio(); window.speechSynthesis?.cancel() }
  const move = (delta: number) => { setIndex(i => nextIndex(i, delta, filtered.length)); resetQuestion() }
  const random = () => { setIndex(Math.floor(Math.random() * filtered.length)); resetQuestion() }
  const speakTts = (clearError = true) => { if (!line || !('speechSynthesis' in window)) return setTtsError('当前浏览器不支持语音合成。')
    if (clearError) setTtsError(''); speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(line.en); u.lang = 'en-US'; u.rate = rate
    const voice = speechSynthesis.getVoices().find(v => v.lang.toLowerCase().startsWith('en')); if (voice) u.voice = voice
    speechSynthesis.speak(u) }
  const speak = () => { if (!line) return; stopAudio(); window.speechSynthesis?.cancel(); setTtsError('')
    if (!line.audio) return speakTts()
    const audio = new Audio(`${import.meta.env.BASE_URL}${line.audio}`); audio.playbackRate = rate; audioRef.current = audio
    const fallback = () => { if (!mountedRef.current || audioRef.current !== audio) return; audioRef.current = null; audio.onerror = null; setTtsError('原声加载失败，已改用浏览器语音。'); speakTts(false) }
    audio.onerror = fallback; void audio.play().catch(fallback) }
  const submit = () => { if (!answer.trim() || !line) return; const next = compareAnswer(answer, line.en); setResult(next); setSession(s => updateProgress(s, line.id, next.correct && !revealed)) }
  const switchMode = (next: Mode) => { setMode(next); resetQuestion() }
  const accuracy = session.completed ? Math.round(session.correct / session.completed * 100) : 0
  return <div class="app-shell">
    <header class="topbar"><a class="brand" href="https://github.com/zhaoolee/hades" aria-label="Hades 仓库"><span class="laurel">Ω</span><span><strong>HADES</strong><small>LISTENER</small></span></a>
      <div class="mode-switch" role="group" aria-label="学习模式"><button class={mode==='browse'?'active':''} onClick={()=>switchMode('browse')} aria-label="查看模式">查看</button><button class={mode==='dictation'?'active':''} onClick={()=>switchMode('dictation')} aria-label="听写模式">听写</button></div>
    </header>
    <main>
      <section class="hero"><p class="eyebrow">ESCAPE THROUGH LANGUAGE</p><h1>在冥界，听懂每一句。</h1><p>收录完整 Hades 中英台词，用浏览器英文语音练习听写。</p></section>
      {error ? <div class="state-card"><p>{error}</p><button onClick={fetchData}>重新加载</button></div> : !data ? <div class="state-card"><span class="loader"/>正在载入冥界档案…</div> : <>
        <section class="controls" aria-label="台词筛选"><label>角色<select value={channel} onChange={e=>setChannel(e.currentTarget.value)}><option value="all">全部角色 · {data.count}</option>{channels.map(c=><option value={c}>{c}</option>)}</select></label><label class="search">搜索<input value={query} onInput={e=>setQuery(e.currentTarget.value)} placeholder="英文、中文、角色或 ID"/></label><label>语速<select value={rate} onChange={e=>setRate(Number(e.currentTarget.value))}><option value="0.7">慢速 · 0.7×</option><option value="0.85">练习 · 0.85×</option><option value="1">正常 · 1×</option></select></label></section>
        {!line ? <div class="state-card">没有找到匹配的台词。</div> : <section class="study-card">
          <div class="card-meta"><span class="speaker">{line.speaker || line.channel}</span><span>{index+1} / {filtered.length}</span><code>{line.id}</code></div>
          <div class="voice-row"><button class="play" onClick={speak} aria-label="播放英文台词"><span>▶</span> {mode==='dictation'?'播放题目':'朗读英文'}</button><span class="tts-note">{line.audio?'游戏原声 · 本地提取':'浏览器英文语音 · 非游戏原声'}</span></div>{ttsError&&<p class="error">{ttsError}</p>}
          <div class={`dialogue-stage ${line.portrait?'has-portrait':''}`}>{line.portrait&&<img class="character-portrait" src={`${import.meta.env.BASE_URL}${line.portrait}`} alt={`${line.speaker || line.channel} 人物立绘`}/>} {mode === 'browse' ? <div class="dialogue"><p class="english">{line.en}</p><div class="divider"/><p class="chinese">{line.zh}</p></div> : <div class="dictation"><p class="hint-label">中文提示</p><p class="chinese">{line.zh}</p>{revealed && !result && <div class="answer-reveal"><small>答案</small>{line.en}</div>}
            <label class="answer-label">你的听写<textarea aria-label="输入你听到的英文台词" value={answer} onInput={e=>setAnswer(e.currentTarget.value)} onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')submit()}} placeholder="听完后，在这里输入英文…" spellcheck={false}/></label>
            {!result ? <div class="submit-row"><button class="primary" onClick={submit} disabled={!answer.trim()}>提交答案</button><button class="ghost" onClick={()=>setRevealed(true)}>显示答案</button></div> : <div class={`feedback ${result.correct&&!revealed?'success':'retry'}`} aria-live="polite"><h2>{result.correct&&!revealed?'✓ 完全正确':'再试一次'}</h2><p class="diff">{result.parts.map((p,i)=><span key={i} class={p.kind}>{p.text} </span>)}</p><small>绿色为正确内容，红色删除线为多余内容，金色为遗漏内容。</small><div class="submit-row"><button class="primary" onClick={()=>move(1)}>下一句</button><button class="ghost" onClick={resetQuestion}>重试</button></div></div>}
          </div>}</div>
          <nav class="navigation" aria-label="台词导航"><button onClick={()=>move(-1)}>← 上一句</button><button onClick={random}>随机一句</button><button onClick={()=>move(1)}>下一句 →</button></nav>
        </section>}
        <section class="stats"><div><strong>{session.completed}</strong><span>已完成</span></div><div><strong>{session.correct}</strong><span>正确</span></div><div><strong>{accuracy}%</strong><span>正确率</span></div><div><strong>{session.reviewIds.length}</strong><span>待复习</span></div></section>
      </>}
    </main><footer>Death is only the beginning. · 学习进度仅保存在当前浏览器</footer>
  </div>
}
