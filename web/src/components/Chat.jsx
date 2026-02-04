import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function Chat() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function sendPrompt(e) {
    e.preventDefault()
    if (!input.trim()) return

    const prompt = input.trim()
    setMessages((m) => [...m, { role: 'user', text: prompt }])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      })

      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        const msg = detail?.detail || res.statusText || 'Request failed'
        throw new Error(msg)
      }

      const payload = await res.json()
      setMessages((m) => [...m, { role: 'assistant', text: payload.text }])
    } catch (err) {
      setError(err.message)
      setMessages((m) => [...m, { role: 'assistant', text: '**Error:** ' + err.message }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-box">
        <div className="messages">
          {messages.length === 0 && <div className="empty">Send a prompt to start the assistant.</div>}

          {messages.map((m, idx) => (
            <div key={idx} className={`message ${m.role}`}>
              <div className="bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
              </div>
            </div>
          ))}
        </div>

        <form className="input-row" onSubmit={sendPrompt}>
          <input
            aria-label="Prompt"
            placeholder="Ask to find or book a padel slot e.g. 'Find a 90-minute double court at lemon-padel-club tomorrow between 18:00 and 20:00'"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            {loading ? 'Waiting...' : 'Send'}
          </button>
        </form>
        {loading && (
          <div className="loading">
            <div className="spinner" />
            <div className="loading-text">Agent is processing your request...</div>
          </div>
        )}
        {error && <div className="error">{error}</div>}
      </div>
    </div>
  )
}
