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
  const [openPopover, setOpenPopover] = useState(null) // slot_id of open attendee popover
  const timerRef = useRef(null)

  useEffect(() => {
    if (openPopover === null) return
    const close = () => setOpenPopover(null)
    document.addEventListener('click', close, { capture: true, once: true })
    return () => document.removeEventListener('click', close, { capture: true })
  }, [openPopover])

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
      setSession(prev => prev ? { ...prev, tally: data.tally, voter_count: data.voter_count, voters: data.voters, attendees: data.attendees } : prev)
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

  // Set of slot IDs that have reached their threshold
  const winners = new Set(
    session?.slots
      .filter(s => (session.tally[s.slot_id] || 0) >= threshold(s.court_type))
      .map(s => s.slot_id) ?? []
  )

  return (
    <div className="find-container">
      <h2 style={{ margin: '0 0 14px', fontSize: '1.1rem' }}>🗳️ {t('votePage.title')}</h2>

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

      {/* Voter list */}
      {session?.voters?.length > 0 && (
        <p style={{ margin: '0 0 12px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          {session.voters.join(' · ')}
        </p>
      )}

      {/* Slot list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {session?.slots.map(slot => {
          const yesCount = session.tally[slot.slot_id] || 0
          const slotAttendees = session.attendees?.[slot.slot_id] ?? []
          const total = session.voter_count
          const thresh = threshold(slot.court_type)
          const pct = Math.min(100, Math.round((yesCount / thresh) * 100))
          const isWinner = winners.has(slot.slot_id)
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
                <span className="find-slot-court" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '200px' }}>{slot.court}</span>
                <span className="find-slot-meta">{slot.duration} min</span>
                <span className="find-slot-price">{slot.price}</span>
                <span style={{ marginLeft: 'auto', position: 'relative' }}>
                  <button
                    onClick={() => slotAttendees.length > 0 && setOpenPopover(openPopover === slot.slot_id ? null : slot.slot_id)}
                    style={{
                      background: 'none', border: 'none', padding: 0,
                      fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap',
                      cursor: slotAttendees.length > 0 ? 'pointer' : 'default',
                      textDecoration: 'none',
                    }}
                  >
                    {t('votePage.attendees')}: {yesCount}/{thresh}
                  </button>
                  {openPopover === slot.slot_id && (
                    <div
                      onClick={() => setOpenPopover(null)}
                      style={{
                        position: 'absolute', right: 0, top: '100%', marginTop: '6px', zIndex: 10,
                        background: 'var(--bg-surface)', border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-sm)', padding: '8px 12px',
                        fontSize: '0.8rem', color: 'var(--text-primary)', whiteSpace: 'nowrap',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                      }}
                    >
                      {slotAttendees.join(', ')}
                    </div>
                  )}
                </span>
              </div>

              {/* Progress bar */}
              <div style={{ width: '100%', height: '4px', borderRadius: '2px', background: 'var(--border-color)' }}>
                <div style={{
                  height: '100%', borderRadius: '2px', background: 'var(--accent)',
                  width: `${pct}%`, transition: 'width 0.4s ease',
                }} />
              </div>

              {/* Can / Can't buttons + book button */}
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', width: '100%' }}>
                <button
                  style={{
                    padding: '4px 12px', fontSize: '0.8rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                    border: `1px solid ${myAnswer === true ? 'rgb(22,163,74)' : 'var(--border-color)'}`,
                    background: myAnswer === true ? 'rgba(22,163,74,0.12)' : 'var(--bg-surface-raised)',
                    color: 'var(--text-primary)',
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
                    border: `1px solid ${myAnswer === false ? 'rgb(220,38,38)' : 'var(--border-color)'}`,
                    background: myAnswer === false ? 'rgba(220,38,38,0.1)' : 'var(--bg-surface-raised)',
                    color: 'var(--text-primary)',
                    fontWeight: myAnswer === false ? 600 : 400,
                  }}
                  disabled={submittedVotes !== null}
                  onClick={() => setPendingVotes(prev => ({ ...prev, [slot.slot_id]: false }))}
                >
                  ✗ {t('votePage.cant_attend')}
                </button>
                <a
                  href={isWinner ? slot.booking_link : undefined}
                  className="find-book-btn"
                  style={{ marginLeft: 'auto', visibility: isWinner ? 'visible' : 'hidden', pointerEvents: isWinner ? 'auto' : 'none' }}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t('votePage.book_btn')}
                </a>
              </div>
            </div>
          )
        })}
      </div>

      {/* Submit / Change row */}
      <div style={{ marginTop: '14px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        {submittedVotes === null ? (
          <button
            className="find-submit"
            style={{ margin: 0, opacity: (!voterName.trim() || !allAnswered) ? 0.5 : 1 }}
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
