import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'

// Court-type-aware consensus threshold
function threshold(courtType) {
  return courtType === 'SINGLE' ? 2 : 4
}

export default function VotePage({ voteId }) {
  const { t } = useTranslation()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [voterName, setVoterName] = useState('')
  const [pendingVotes, setPendingVotes] = useState({})   // {slot_id: true|false} before submit
  const [submittedVotes, setSubmittedVotes] = useState(null) // {slot_id: bool} after submit
  const [submitting, setSubmitting] = useState(false)
  const timerRef = useRef(null)

  const fetchSession = useCallback(async () => {
    try {
      const res = await fetch(`/api/votes/${voteId}`)
      if (res.status === 404) {
        setNotFound(true)
        if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
        return
      }
      if (!res.ok) return
      setSession(await res.json())
    } finally {
      setLoading(false)
    }
  }, [voteId])

  useEffect(() => {
    fetchSession()
    timerRef.current = setInterval(fetchSession, 3000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [fetchSession])

  async function handleSubmitVotes() {
    if (!voterName.trim() || submitting) return
    setSubmitting(true)
    try {
      const votes = session.slots.map(s => ({
        slot_id: s.slot_id,
        can_attend: pendingVotes[s.slot_id] === true,
      }))
      const res = await fetch(`/api/votes/${voteId}/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voter_name: voterName.trim(), votes }),
      })
      if (!res.ok) return
      const data = await res.json()
      setSession(prev => prev ? { ...prev, tally: data.tally, voter_count: data.voter_count } : prev)
      setSubmittedVotes({ ...pendingVotes })
    } finally {
      setSubmitting(false)
    }
  }

  function handleChangeVote() {
    setPendingVotes({ ...submittedVotes })
    setSubmittedVotes(null)
  }

  if (loading) return <div className="find-container"><p className="find-summary">{t('votePage.loading')}</p></div>
  if (notFound) return <div className="find-container"><p className="find-error">{t('votePage.not_found')}</p></div>

  const allAnswered = session?.slots.every(s => pendingVotes[s.slot_id] !== undefined)

  // Find winning slot (first to reach its threshold)
  const winner = session?.slots.find(s =>
    (session.tally[s.slot_id] || 0) >= threshold(s.court_type)
  )

  return (
    <div className="find-container">
      <h2 style={{ margin: '0 0 4px', fontSize: '1.1rem' }}>🗳️ {t('votePage.title')}</h2>
      <p style={{ margin: '0 0 14px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        {t('votePage.tagline')}
      </p>

      {/* Consensus banner */}
      {winner && (
        <div className="find-summary" style={{ marginBottom: '16px', background: 'var(--accent-subtle)', borderColor: 'rgba(6,182,212,0.4)' }}>
          <strong>{t('votePage.consensus_title')}</strong><br />
          <span style={{ fontSize: '0.85rem' }}>{t('votePage.consensus_body')}</span>{' '}
          <a href={winner.booking_link} className="find-book-btn" target="_blank" rel="noopener noreferrer">
            {t('votePage.book_btn')}
          </a>
        </div>
      )}

      {/* Name input (shown until votes submitted) */}
      {submittedVotes === null && (
        <div className="find-field" style={{ marginBottom: '14px' }}>
          <label>{t('votePage.your_name')}</label>
          <input
            type="text"
            value={voterName}
            onChange={e => setVoterName(e.target.value)}
            placeholder={t('votePage.name_placeholder')}
            maxLength={40}
          />
        </div>
      )}

      {/* Slot list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {session?.slots.map(slot => {
          const yesCount = session.tally[slot.slot_id] || 0
          const total = session.voter_count
          const thresh = threshold(slot.court_type)
          const pct = Math.min(100, Math.round((yesCount / thresh) * 100))
          const isWinner = winner?.slot_id === slot.slot_id
          const myAnswer = submittedVotes !== null ? submittedVotes[slot.slot_id] : pendingVotes[slot.slot_id]

          return (
            <div
              key={slot.slot_id}
              className="find-slot"
              style={{
                flexDirection: 'column', alignItems: 'flex-start', gap: '6px',
                borderColor: isWinner ? 'rgba(6,182,212,0.5)' : undefined,
                background: isWinner ? 'var(--accent-subtle)' : undefined,
              }}
            >
              {/* Slot header */}
              <div style={{ display: 'flex', width: '100%', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <span className="find-slot-time">{slot.date} {slot.local_time}</span>
                <span className="find-slot-court">{slot.court}</span>
                <span className="find-slot-meta">{slot.duration} min</span>
                <span className="find-slot-price">{slot.price}</span>
                <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                  {t('votePage.can_attend_count', { count: yesCount })}{total > 0 ? ` / ${total}` : ''}
                </span>
              </div>

              {/* Progress bar */}
              <div style={{ width: '100%', height: '4px', borderRadius: '2px', background: 'var(--border-color)' }}>
                <div style={{
                  height: '100%', borderRadius: '2px', background: 'var(--accent)',
                  width: `${pct}%`, transition: 'width 0.4s ease',
                }} />
              </div>

              {/* Can / Can't buttons */}
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  style={{
                    padding: '4px 12px', fontSize: '0.8rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                    border: `1px solid ${myAnswer === true ? 'rgba(34,197,94,0.7)' : 'var(--border-color)'}`,
                    background: myAnswer === true ? 'rgba(34,197,94,0.15)' : 'var(--bg-surface-raised)',
                    color: myAnswer === true ? 'rgb(134,239,172)' : 'var(--text-secondary)',
                    fontWeight: myAnswer === true ? 600 : 400,
                  }}
                  disabled={submittedVotes !== null}
                  onClick={() => setPendingVotes(prev => ({ ...prev, [slot.slot_id]: true }))}
                >
                  ✓ {t('votePage.can_attend')}
                </button>
                <button
                  style={{
                    padding: '4px 12px', fontSize: '0.8rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                    border: `1px solid ${myAnswer === false ? 'rgba(239,68,68,0.7)' : 'var(--border-color)'}`,
                    background: myAnswer === false ? 'rgba(239,68,68,0.12)' : 'var(--bg-surface-raised)',
                    color: myAnswer === false ? 'rgb(252,165,165)' : 'var(--text-secondary)',
                    fontWeight: myAnswer === false ? 600 : 400,
                  }}
                  disabled={submittedVotes !== null}
                  onClick={() => setPendingVotes(prev => ({ ...prev, [slot.slot_id]: false }))}
                >
                  ✗ {t('votePage.cant_attend')}
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Submit / Change row */}
      <div style={{ marginTop: '14px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        {submittedVotes === null ? (
          <button
            className="find-book-btn"
            style={{ padding: '8px 20px', fontSize: '0.875rem', opacity: (!voterName.trim() || !allAnswered) ? 0.5 : 1 }}
            disabled={!voterName.trim() || !allAnswered || submitting}
            onClick={handleSubmitVotes}
          >
            {submitting ? t('votePage.submitting') : t('votePage.submit_btn')}
          </button>
        ) : (
          <>
            <span style={{ fontSize: '0.8rem', color: 'var(--accent)' }}>{t('votePage.submitted_label')}</span>
            <button className="suggestion-chip" onClick={handleChangeVote}>
              {t('votePage.change_vote')}
            </button>
          </>
        )}
      </div>

      <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '16px' }}>
        {t('votePage.expires_note')}
      </p>
    </div>
  )
}
