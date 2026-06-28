import { useEffect, useRef, useState } from 'react'
import api from '../api/client'

// ---- types ------------------------------------------------------------------

interface Message {
  role:    'user' | 'assistant'
  content: string
}

// ---- helpers ----------------------------------------------------------------

function Bubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-sm'
            : 'bg-white border border-slate-200 text-slate-800 rounded-bl-sm shadow-sm'
        }`}
      >
        {msg.content}
      </div>
    </div>
  )
}

const SUGGESTIONS = [
  'What is my food cost percentage this month?',
  'Which menu item has the highest food cost?',
  'Am I hitting my 30% food cost target?',
  'What should I focus on to improve profitability?',
]

// ---- page -------------------------------------------------------------------

export function AskPage() {
  const [messages,  setMessages]  = useState<Message[]>([])
  const [input,     setInput]     = useState('')
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send(question: string) {
    const q = question.trim()
    if (!q || loading) return

    const userMsg: Message = { role: 'user', content: q }
    const next = [...messages, userMsg]
    setMessages(next)
    setInput('')
    setLoading(true)
    setError('')

    // Build conversation history for multi-turn (exclude last user message —
    // the service prepends fresh context to each call).
    const history = next.slice(0, -1).map(m => ({
      role:    m.role,
      content: m.content,
    }))

    try {
      const res = await api.post('/ai/ask', {
        question,
        conversation_history: history,
      })
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.answer }])
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? err?.message ?? 'Request failed'
      setError(detail)
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className='flex flex-col h-full bg-slate-50'>

      {/* Header */}
      <div className='px-6 py-4 bg-white border-b border-slate-200 shrink-0'>
        <h1 className='text-lg font-bold text-slate-800'>Ask your data</h1>
        <p className='text-xs text-slate-400 mt-0.5'>
          Powered by Claude · answers are grounded in your live restaurant data
        </p>
      </div>

      {/* Message list */}
      <div className='flex-1 overflow-y-auto px-6 py-6 space-y-4'>

        {isEmpty && (
          <div className='max-w-xl mx-auto pt-8'>
            <p className='text-sm text-slate-500 mb-4 text-center'>
              Ask anything about your food cost, profitability, or inventory.
            </p>
            <div className='grid grid-cols-1 sm:grid-cols-2 gap-2'>
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className='text-left text-sm px-4 py-3 bg-white border border-slate-200
                             rounded-xl hover:border-blue-300 hover:shadow-sm transition-all
                             text-slate-600'
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => <Bubble key={i} msg={msg} />)}

        {loading && (
          <div className='flex justify-start'>
            <div className='bg-white border border-slate-200 rounded-2xl rounded-bl-sm
                            px-4 py-3 shadow-sm flex gap-1 items-center'>
              <span className='w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:0ms]' />
              <span className='w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:150ms]' />
              <span className='w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:300ms]' />
            </div>
          </div>
        )}

        {error && (
          <div className='text-sm text-red-500 bg-red-50 border border-red-200 rounded-lg px-4 py-2'>
            {error.includes('ANTHROPIC_API_KEY') || error.includes('authentication')
              ? 'LLM service unavailable — add ANTHROPIC_API_KEY to backend/.env and restart the server.'
              : error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className='px-6 py-4 bg-white border-t border-slate-200 shrink-0'>
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className='text-xs text-slate-400 hover:text-slate-600 mb-2 block'
          >
            Clear conversation
          </button>
        )}
        <div className='flex gap-3 items-end'>
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='Ask about food cost, menu profitability, inventory…'
            className='flex-1 border border-slate-300 rounded-xl px-4 py-3 text-sm resize-none
                       focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100
                       max-h-32 overflow-y-auto'
            style={{ fieldSizing: 'content' } as React.CSSProperties}
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className='shrink-0 bg-blue-600 text-white px-5 py-3 rounded-xl text-sm font-semibold
                       hover:bg-blue-700 disabled:opacity-40 transition-opacity'
          >
            Ask
          </button>
        </div>
        <p className='text-xs text-slate-400 mt-2'>
          Enter to send · Shift+Enter for new line
        </p>
      </div>

    </div>
  )
}
