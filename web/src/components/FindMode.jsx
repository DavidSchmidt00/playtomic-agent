import { useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'

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

  // Group results by date
  const grouped = results
    ? results.reduce((acc, slot) => {
        if (!acc[slot.date]) acc[slot.date] = []
        acc[slot.date].push(slot)
        return acc
      }, {})
    : null

  return (
    <div className="find-container">
      {/* Collapsed summary bar */}
      {!formExpanded && (
        <button className="find-filter-summary-bar" onClick={() => setFormExpanded(true)}>
          <span className="find-filter-summary-text">{getSearchSummary()}</span>
          <span className="find-filter-edit-label">{t('findMode.edit_search')} ✏️</span>
        </button>
      )}

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
          <div className="find-field--row">
            <div className="find-field">
              <label>{t('findMode.date_from')}</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => handleDateFromChange(e.target.value)}
                required
              />
            </div>
            <div className="find-field">
              <label>{t('findMode.date_to')}</label>
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

          <button type="submit" className="find-submit" disabled={loading}>
            {loading ? t('findMode.searching') : t('findMode.search_btn')}
          </button>
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
  )
}
