import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import usePresets from '../hooks/usePresets'

const DAY_KEYS = [0, 1, 2, 3, 4, 5, 6]

function formatDayLabel(dateStr, lang) {
  // T12:00:00 avoids DST midnight-shift issues when parsing local dates
  const d = new Date(dateStr + 'T12:00:00')
  const weekday = new Intl.DateTimeFormat(lang, { weekday: 'short' }).format(d)
  const day = d.getDate().toString().padStart(2, '0')
  const month = (d.getMonth() + 1).toString().padStart(2, '0')
  return `${weekday} ${day}.${month}`
}

function formatShortDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00')
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`
}

function addDays(dateStr, days) {
  // T12:00:00 avoids DST midnight-shift issues when parsing local dates
  const d = new Date(dateStr + 'T12:00:00')
  d.setDate(d.getDate() + days)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function FindMode({ region, profile }) {
  const { t, i18n } = useTranslation()

  const [clubName, setClubName] = useState(profile?.preferred_club_name || '')
  const [clubSlug, setClubSlug] = useState(profile?.preferred_club_slug || '')
  const [clubOptions, setClubOptions] = useState([])
  const [clubSearching, setClubSearching] = useState(false)
  const clubDebounceRef = useRef(null)
  const containerRef = useRef(null)
  const [dateFrom, setDateFrom] = useState(todayStr())
  const [dateTo, setDateTo] = useState(addDays(todayStr(), 6))
  const [duration, setDuration] = useState('')
  const [courtType, setCourtType] = useState('')
  const [windows, setWindows] = useState([
    { days: [0, 1, 2, 3, 4], start: '18:00', end: '22:00' },
  ])
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)
  const [formExpanded, setFormExpanded] = useState(true)
  const [voteMode, setVoteMode] = useState(false)
  const [selected, setSelected] = useState({})
  const [voteUrl, setVoteUrl] = useState(null)
  const [voteLoading, setVoteLoading] = useState(false)
  const [voteError, setVoteError] = useState(null)
  const [voteCopied, setVoteCopied] = useState(false)
  const { presets, savePreset, deletePreset } = usePresets()
  const [newPresetName, setNewPresetName] = useState('')
  const [showSavePreset, setShowSavePreset] = useState(false)
  const presetInputRef = useRef(null)

  useEffect(() => {
    if (showSavePreset && presetInputRef.current) {
      presetInputRef.current.focus()
    }
  }, [showSavePreset])
  function handleSavePreset() {
    if (!newPresetName.trim()) return
    const today = new Date(todayStr() + 'T12:00:00')
    const from = new Date(dateFrom + 'T12:00:00')
    const to = new Date(dateTo + 'T12:00:00')
    const offsetFrom = Math.round((from - today) / (1000 * 60 * 60 * 24))
    const offsetTo = Math.round((to - today) / (1000 * 60 * 60 * 24))

    savePreset(newPresetName, {
      clubName,
      clubSlug,
      duration,
      courtType,
      windows,
      offsetFrom,
      offsetTo
    })
    setNewPresetName('')
  }

  function handleLoadPreset(settings) {
    if (!settings) return
    setClubName(settings.clubName || '')
    setClubSlug(settings.clubSlug || '')
    setDuration(settings.duration || '')
    setCourtType(settings.courtType || '')
    setWindows(settings.windows || [])

    const currentToday = todayStr()
    if (settings.offsetFrom !== undefined) {
      setDateFrom(addDays(currentToday, settings.offsetFrom))
    }
    if (settings.offsetTo !== undefined) {
      setDateTo(addDays(currentToday, settings.offsetTo))
    }
  }

  function getSearchSummary() {
    const dateRange = `${formatShortDate(dateFrom)} – ${formatShortDate(dateTo)}`
    const windowTexts = windows
      .map((w) => {
        const days = w.days.map((d) => t(`findMode.days.${d}`)).join(' ')
        return `${days} ${w.start}–${w.end}`
      })
      .join(', ')
    return `${clubName} · ${dateRange} · ${windowTexts}`
  }

  function handleClubNameChange(val) {
    setClubName(val)
    setClubSlug('')
    setClubOptions([])
    if (clubDebounceRef.current) clearTimeout(clubDebounceRef.current)
    if (val.length < 2) return
    clubDebounceRef.current = setTimeout(async () => {
      setClubSearching(true)
      try {
        const res = await fetch(`/api/clubs?q=${encodeURIComponent(val)}`)
        if (res.ok) setClubOptions(await res.json())
      } catch {
        // ignore transient search errors
      } finally {
        setClubSearching(false)
      }
    }, 300)
  }

  function selectClub(club) {
    setClubName(club.name)
    setClubSlug(club.slug)
    setClubOptions([])
  }

  function handleDateFromChange(val) {
    setDateFrom(val)
    const maxTo = addDays(val, 13)
    if (dateTo > maxTo) setDateTo(maxTo)
    if (dateTo < val) setDateTo(val)
  }

  function addWindow() {
    setWindows((prev) => [...prev, { days: [], start: '18:00', end: '22:00' }])
  }

  function removeWindow(idx) {
    setWindows((prev) => prev.filter((_, i) => i !== idx))
  }

  function toggleDay(winIdx, day) {
    setWindows((prev) =>
      prev.map((w, i) => {
        if (i !== winIdx) return w
        const days = w.days.includes(day) ? w.days.filter((d) => d !== day) : [...w.days, day]
        return { ...w, days }
      })
    )
  }

  function updateWindowTime(winIdx, field, val) {
    setWindows((prev) =>
      prev.map((w, i) => (i === winIdx ? { ...w, [field]: val } : w))
    )
  }

  function handleClearSearch() {
    setClubName(profile?.preferred_club_name || '')
    setClubSlug(profile?.preferred_club_slug || '')
    setClubOptions([])
    setDateFrom(todayStr())
    setDateTo(addDays(todayStr(), 6))
    setDuration('')
    setCourtType('')
    setWindows([{ days: [0, 1, 2, 3, 4], start: '18:00', end: '22:00' }])
    setResults(null)
    setSummary(null)
    setError(null)
    setFormExpanded(true)
  }
  async function handleSearch(e) {
    e.preventDefault()
    if (!clubSlug) {
      setError(t('findMode.club_not_selected'))
      return
    }

    setLoading(true)
    setError(null)
    setResults(null)
    setSummary(null)

    try {
      const body = {
        club_slug: clubSlug,
        date_from: dateFrom,
        date_to: dateTo,
        time_windows: windows,
        timezone: region?.timezone || undefined,
        language: region?.language || undefined,
        country: region?.country || undefined,
      }
      if (duration) body.duration = parseInt(duration, 10)
      if (courtType) body.court_type = courtType

      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}))
        throw new Error(errBody.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setResults(data.results)
      setSummary({ count: data.total_count, days: data.dates_checked })
      setFormExpanded(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function slotKey(slot) {
    return `${slot.date}_${slot.local_time}_${slot.court}_${slot.duration}`
  }

  function handleOpenVoteMode() {
    const init = {}
    results.forEach(slot => { init[slotKey(slot)] = true })
    setSelected(init)
    setVoteUrl(null)
    setVoteError(null)
    setVoteCopied(false)
    setVoteMode(true)
  }

  function toggleSlotSelection(slotId) {
    setSelected(prev => ({ ...prev, [slotId]: !prev[slotId] }))
  }

  function selectAll(val) {
    setSelected(prev => Object.fromEntries(Object.keys(prev).map(k => [k, val])))
  }

  async function handleCreateVote() {
    const slotsWithIds = results.map(slot => ({ ...slot, slot_id: slotKey(slot) }))
    const chosenSlots = slotsWithIds.filter(s => selected[s.slot_id])
    if (chosenSlots.length === 0) {
      setVoteError(t('vote.no_slots_selected'))
      return
    }
    setVoteLoading(true)
    setVoteError(null)
    try {
      const res = await fetch('/api/votes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slots: chosenSlots }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const shareUrl = `${window.location.origin}/vote/${data.vote_id}`
      setVoteUrl(shareUrl)
      await navigator.clipboard.writeText(shareUrl).catch(() => {})
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch {
      setVoteError(t('vote.error'))
    } finally {
      setVoteLoading(false)
    }
  }

  function handleCopyVoteUrl() {
    navigator.clipboard.writeText(voteUrl).catch(() => {})
    setVoteCopied(true)
    setTimeout(() => setVoteCopied(false), 2000)
  }

  // Group results by date
  const grouped = results
    ? results.reduce((acc, slot) => {
      if (!acc[slot.date]) acc[slot.date] = []
      acc[slot.date].push(slot)
      return acc
    }, {})
    : null

  return (
    <div className="find-mode-root">
      {/* Collapsed summary bar — outside scroll area so it never scrolls away */}
      {!formExpanded && (
        <div className="find-filter-bar-outer">
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', minWidth: 0 }}>
            <button className="find-filter-summary-bar" style={{ flex: 1, minWidth: 0, overflow: 'hidden' }} onClick={() => setFormExpanded(true)}>
              <span className="find-filter-summary-text">{getSearchSummary()}</span>
              <span className="find-filter-edit-label">{t('findMode.edit_search')} ✏️</span>
            </button>
            <button
              type="button"
              className="clear-chat-btn"
              onClick={handleClearSearch}
              title={t('findMode.clear_search', { defaultValue: 'Clear search' })}
            >
              🗑️
            </button>
          </div>
        </div>
      )}

    <div className="find-container" ref={containerRef}>
      {/* Expandable form */}
      {formExpanded && (
        <form className="find-form" onSubmit={handleSearch}>
          {/* Club search autocomplete */}
          <div className="find-field">
            <label>{t('findMode.club_label')}</label>
            <div className="find-club-wrap">
              <input
                type="text"
                value={clubName}
                onChange={(e) => handleClubNameChange(e.target.value)}
                onBlur={() => setTimeout(() => setClubOptions([]), 150)}
                placeholder={t('findMode.club_placeholder')}
                autoComplete="off"
                className={clubSlug ? 'find-club-confirmed' : ''}
              />
              {clubSearching && <span className="find-club-spinner">{t('findMode.club_searching')}</span>}
              {clubOptions.length > 0 && (
                <ul className="find-club-dropdown">
                  {clubOptions.map((c) => (
                    <li key={c.slug} onMouseDown={() => selectClub(c)}>
                      {c.name}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Date range */}
          <div className="find-field">
            <label>{t('findMode.date_from')}</label>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '4px' }}>
              {[
                { label: t('findMode.next_7_days', { defaultValue: 'Next 7 days' }), days: 6 },
                { label: t('findMode.next_2_weeks', { defaultValue: 'Next 2 weeks' }), days: 13 },
              ].map(({ label, days }) => {
                const today = todayStr()
                const end = addDays(today, days)
                const active = dateFrom === today && dateTo === end
                return (
                  <button
                    key={days}
                    type="button"
                    onClick={() => { setDateFrom(today); setDateTo(end) }}
                    className="suggestion-chip"
                    style={active ? { background: 'var(--accent-subtle)', borderColor: 'rgba(6,182,212,0.4)', color: 'var(--accent)' } : {}}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
            <div className="find-field--row" style={{ margin: 0 }}>
              <div className="find-field" style={{ gap: 0 }}>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => handleDateFromChange(e.target.value)}
                  required
                />
              </div>
              <div className="find-field" style={{ gap: 0 }}>
                <input
                  type="date"
                  value={dateTo}
                  min={dateFrom}
                  max={addDays(dateFrom, 13)}
                  onChange={(e) => setDateTo(e.target.value)}
                  required
                />
              </div>
            </div>
          </div>

          {/* Duration + Court type */}
          <div className="find-field--row">
            <div className="find-field">
              <label>{t('findMode.duration')}</label>
              <select value={duration} onChange={(e) => setDuration(e.target.value)}>
                <option value="">{t('findMode.any_duration')}</option>
                <option value="60">60 min</option>
                <option value="90">90 min</option>
                <option value="120">120 min</option>
              </select>
            </div>
            <div className="find-field">
              <label>{t('findMode.court_type')}</label>
              <select value={courtType} onChange={(e) => setCourtType(e.target.value)}>
                <option value="">{t('findMode.any_court')}</option>
                <option value="SINGLE">{t('findMode.single')}</option>
                <option value="DOUBLE">{t('findMode.double')}</option>
              </select>
            </div>
          </div>

          {/* Time windows */}
          <div className="find-field">
            <label>{t('findMode.time_windows')}</label>
            {windows.map((w, idx) => (
              <div key={idx} className="find-window">
                <div className="find-window-days">
                  {DAY_KEYS.map((day) => (
                    <button
                      key={day}
                      type="button"
                      className={`day-btn${w.days.includes(day) ? ' active' : ''}`}
                      onClick={() => toggleDay(idx, day)}
                    >
                      {t(`findMode.days.${day}`)}
                    </button>
                  ))}
                </div>
                <div className="find-window-times">
                  <span>{t('findMode.from_time')}</span>
                  <input
                    type="time"
                    value={w.start}
                    onChange={(e) => updateWindowTime(idx, 'start', e.target.value)}
                  />
                  <span>{t('findMode.to_time')}</span>
                  <input
                    type="time"
                    value={w.end}
                    onChange={(e) => updateWindowTime(idx, 'end', e.target.value)}
                  />
                  {windows.length > 1 && (
                    <button type="button" className="find-remove-btn" onClick={() => removeWindow(idx)}>
                      {t('findMode.remove_window')}
                    </button>
                  )}
                </div>
              </div>
            ))}
            <button type="button" className="find-add-btn" onClick={addWindow}>
              {t('findMode.add_window')}
            </button>
          </div>

          {/* Bottom action row: Search + Save preset */}
          <div className="find-field" style={{ display: showSavePreset ? 'flex' : 'none', flexDirection: 'row', gap: '8px' }}>
            <input
              ref={presetInputRef}
              type="text"
              placeholder={t('findMode.save_preset_prompt')}
              value={newPresetName}
              onChange={(e) => setNewPresetName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  if (newPresetName.trim()) { handleSavePreset(); setShowSavePreset(false) }
                } else if (e.key === 'Escape') {
                  setNewPresetName(''); setShowSavePreset(false)
                }
              }}
              style={{ flex: 1, margin: 0 }}
            />
            <button
              type="button"
              onMouseDown={(e) => { e.preventDefault(); handleSavePreset(); setShowSavePreset(false) }}
              disabled={!newPresetName.trim()}
              style={{ width: '44px', padding: 0, margin: 0, border: '1px solid var(--accent)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-surface)', color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              ✓
            </button>
            <button
              type="button"
              onMouseDown={(e) => { e.preventDefault(); setNewPresetName(''); setShowSavePreset(false) }}
              style={{ width: '44px', padding: 0, margin: 0, border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-surface-raised)', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              ✕
            </button>
          </div>
          <div style={{ display: showSavePreset ? 'none' : 'flex', gap: '8px', alignItems: 'stretch' }}>
            <button type="submit" className="find-submit" disabled={loading} style={{ flex: 1, margin: 0 }}>
              {loading ? t('findMode.searching') : t('findMode.search_btn')}
            </button>
            <button
              type="button"
              onClick={() => setShowSavePreset(true)}
              title={t('findMode.save_preset_btn')}
              style={{ background: 'var(--bg-surface-raised)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0 0.85rem', color: 'var(--accent)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}
            >
              {t('findMode.save_preset_short')}
            </button>
          </div>

          {/* Preset pills */}
          {presets.length > 0 && !showSavePreset && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
              {presets.map(p => (
                <div key={p.id} style={{ display: 'inline-flex', alignItems: 'center', background: 'var(--accent-subtle)', border: '1px solid rgba(6, 182, 212, 0.2)', borderRadius: '12px', padding: '3px 10px', fontSize: '0.78rem' }}>
                  <span
                    style={{ cursor: 'pointer', paddingRight: '6px', color: 'var(--text-primary)' }}
                    onClick={() => handleLoadPreset(p.settings)}
                  >
                    {p.name}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); deletePreset(p.id) }}
                    style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '0', fontSize: '0.7rem', lineHeight: 1 }}
                    title={t('findMode.delete_preset')}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </form>
      )}

      {error && <div className="find-error">{error}</div>}

      {results !== null && (
        <div className="find-results">
          {summary && summary.count > 0 && (
            <p className="find-summary">
              {t('findMode.results_summary', { count: summary.count, days: summary.days })}
            </p>
          )}

          {results.length > 0 && !voteMode && (
            <button
              type="button"
              style={{
                width: '100%', margin: '8px 0 4px', padding: '0.55rem 1rem',
                background: 'var(--bg-surface)', border: '1px solid rgba(6,182,212,0.4)',
                borderRadius: 'var(--radius-sm)', color: 'var(--accent)',
                fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer',
              }}
              onClick={handleOpenVoteMode}
            >
              {t('vote.start_btn')}
            </button>
          )}

          {voteMode && (
            <div style={{ marginTop: '12px', padding: '12px', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
              {!voteUrl ? (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{t('vote.select_title')}</span>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button type="button" className="suggestion-chip" onClick={() => selectAll(true)}>{t('vote.select_all')}</button>
                      <button type="button" className="suggestion-chip" onClick={() => selectAll(false)}>{t('vote.select_none')}</button>
                    </div>
                  </div>

                  {results.map((slot) => {
                    const sid = slotKey(slot)
                    return (
                      <label key={sid} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', borderBottom: '1px solid var(--border-color)', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={!!selected[sid]}
                          onChange={() => toggleSlotSelection(sid)}
                          style={{ accentColor: 'var(--accent)', width: '16px', height: '16px' }}
                        />
                        <span className="find-slot-meta" style={{ minWidth: '60px' }}>{formatDayLabel(slot.date, region?.language || i18n.language)}</span>
                        <span className="find-slot-time">{slot.local_time}</span>
                        <span className="find-slot-court">{slot.court}</span>
                        <span className="find-slot-meta">{slot.duration} min</span>
                        <span className="find-slot-price">{slot.price}</span>
                      </label>
                    )
                  })}

                  {voteError && <div className="find-error" style={{ marginTop: '6px' }}>{voteError}</div>}

                  <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                    <button
                      type="button"
                      className="find-submit"
                      style={{ flex: 1, margin: 0 }}
                      onClick={handleCreateVote}
                      disabled={voteLoading}
                    >
                      {voteLoading ? t('vote.creating') : t('vote.create_btn')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setVoteMode(false)}
                      style={{ padding: '0 14px', background: 'var(--bg-surface-raised)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', color: 'var(--text-secondary)' }}
                    >
                      {t('vote.close_btn')}
                    </button>
                  </div>
                </>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <span style={{ fontWeight: 600 }}>{t('vote.share_label')}</span>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <code style={{ flex: 1, fontSize: '0.8rem', wordBreak: 'break-all', color: 'var(--accent)' }}>{voteUrl}</code>
                    <button className="find-submit" style={{ flex: '0 0 auto', padding: '6px 14px', margin: 0 }} onClick={handleCopyVoteUrl}>
                      {voteCopied ? t('vote.copied') : t('vote.copy_btn')}
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setVoteMode(false); setVoteUrl(null) }}
                    style={{ alignSelf: 'flex-start', background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.8rem' }}
                  >
                    {t('vote.close_btn')}
                  </button>
                </div>
              )}
            </div>
          )}

          {results.length === 0 ? (
            <p className="find-no-results">{t('findMode.no_results')}</p>
          ) : (
            Object.entries(grouped).map(([date, slots]) => (
              <div key={date} className="find-date-group">
                <div className="find-date-label">{formatDayLabel(date, region?.language || i18n.language)}</div>
                {slots.map((slot, i) => (
                  <div key={i} className="find-slot">
                    <span className="find-slot-time">{slot.local_time}</span>
                    <span className="find-slot-court">{slot.court}</span>
                    <span className="find-slot-meta">{slot.duration} min</span>
                    <span className="find-slot-price">{slot.price}</span>
                    <a
                      href={slot.booking_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="find-book-btn"
                    >
                      {t('findMode.book_btn')}
                    </a>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </div>
    </div>
  )
}
