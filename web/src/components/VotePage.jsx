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
  const [myVote, setMyVote] = useState(null)
  const [voting, setVoting] = useState(false)
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

  async function handleVote(slotId) {
    if (!voterName.trim() || voting) return
    setVoting(true)
    try {
      const res = await fetch(`/api/votes/${voteId}/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voter_name: voterName.trim(), slot_id: slotId }),
      })
      if (!res.ok) return
      const data = await res.json()
      setSession(prev => prev ? { ...prev, tally: data.tally, voter_count: data.voter_count } : prev)
      setMyVote(slotId)
    } finally {
      setVoting(false)
    }
  }

  if (loading) return <div className="find-container"><p className="find-summary">{t('votePage.loading')}</p></div>
  if (notFound) return <div className="find-container"><p className="find-error">{t('votePage.not_found')}</p></div>

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

      {/* Name input (shown until vote cast) */}
      {!myVote && (
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
          const count = session.tally[slot.slot_id] || 0
          const thresh = threshold(slot.court_type)
          const pct = Math.min(100, Math.round((count / thresh) * 100))
          const isMyVote = myVote === slot.slot_id
          const isWinner = winner?.slot_id === slot.slot_id

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
                  {t('votePage.votes_other', { count })} / {thresh}
                </span>
              </div>

              {/* Progress bar */}
              <div style={{ width: '100%', height: '4px', borderRadius: '2px', background: 'var(--border-color)' }}>
                <div style={{
                  height: '100%', borderRadius: '2px', background: 'var(--accent)',
                  width: `${pct}%`, transition: 'width 0.4s ease',
                }} />
              </div>

              {/* Action buttons */}
              {isMyVote ? (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--accent)' }}>{t('votePage.voted_label')}</span>
                  <button
                    className="suggestion-chip"
                    onClick={() => setMyVote(null)}
                  >
                    {t('votePage.change_vote')}
                  </button>
                </div>
              ) : (
                <button
                  className="find-book-btn"
                  style={{ alignSelf: 'flex-start' }}
                  disabled={!voterName.trim() || voting}
                  onClick={() => handleVote(slot.slot_id)}
                >
                  {t('votePage.vote_btn')}
                </button>
              )}
            </div>
          )
        })}
      </div>

      <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '16px' }}>
        {t('votePage.expires_note')}
      </p>
    </div>
  )
}
