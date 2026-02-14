import React, { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import useProfile from '../hooks/useProfile'
import ProfileCard from './ProfileCard'
import ProfileSuggestion from './ProfileSuggestion'

export default function Chat({ region }) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [pendingSuggestions, setPendingSuggestions] = useState(null)
  const messagesEndRef = useRef(null)
  const { profile, updateProfile, removePreference, clearProfile, PROFILE_LABELS } = useProfile()

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function handleAcceptSuggestions() {
    if (pendingSuggestions) {
      for (const s of pendingSuggestions) {
        updateProfile(s.key, s.value)
      }
      setPendingSuggestions(null)
    }
  }

  function handleDismissSuggestions() {
    setPendingSuggestions(null)
  }

  async function sendPrompt(e) {
    e.preventDefault()
    if (!input.trim()) return

    const prompt = input.trim()
    const newUserMsg = { role: 'user', text: prompt }
    const updatedMessages = [...messages, newUserMsg]
    setMessages(updatedMessages)
    setInput('')
    setLoading(true)
    setError(null)

    try {
      // Send full conversation history + user profile + region settings
      const history = updatedMessages.map((m) => ({ role: m.role, content: m.text }))
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: history,
          user_profile: Object.keys(profile).length > 0 ? profile : null,
          country: region?.country || null,
          language: region?.language || 'en',
          timezone: region?.timezone || null,
        }),
      })

      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        const msg = detail?.detail || res.statusText || 'Request failed'
        throw new Error(msg)
      }

      const payload = await res.json()
      setMessages((m) => [...m, { role: 'assistant', text: payload.text }])

      // Handle profile suggestions from the agent
      if (payload.profile_suggestions && payload.profile_suggestions.length > 0) {
        setPendingSuggestions(payload.profile_suggestions)
      }
    } catch (err) {
      setError(err.message)
      setMessages((m) => [...m, { role: 'assistant', text: '**Error:** ' + err.message }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-container">
      <ProfileCard
        profile={profile}
        PROFILE_LABELS={PROFILE_LABELS}
        onRemove={removePreference}
        onClear={clearProfile}
      />
      <div className="chat-box">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              <span className="empty-icon">🎾</span>
              {t('empty_state')}
            </div>
          )}

          {messages.map((m, idx) => (
            <div key={idx} className={`message ${m.role}`}>
              <div className="bubble">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {m.text}
                </ReactMarkdown>
              </div>
            </div>
          ))}

          {pendingSuggestions && (
            <ProfileSuggestion
              suggestions={pendingSuggestions}
              onAccept={handleAcceptSuggestions}
              onDismiss={handleDismissSuggestions}
              PROFILE_LABELS={PROFILE_LABELS}
            />
          )}

          {loading && (
            <div className="message assistant">
              <div className="bubble typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <form className="input-row" onSubmit={sendPrompt}>
          <input
            aria-label="Prompt"
            placeholder={t('placeholder')}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            {loading ? '...' : t('send_btn')}
          </button>
        </form>
        {error && <div className="error">{error}</div>}
      </div>
    </div>
  )
}
