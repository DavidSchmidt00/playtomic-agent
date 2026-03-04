import { useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8082'

const DAY_KEYS = [0, 1, 2, 3, 4, 5, 6]

function formatDayLabel(dateStr, lang) {
  // T12:00:00 avoids DST midnight-shift issues when parsing local dates
  const d = new Date(dateStr + 'T12:00:00')
  const weekday = new Intl.DateTimeFormat(lang, { weekday: 'short' }).format(d)
  const day = d.getDate().toString().padStart(2, '0')
  const month = (d.getMonth() + 1).toString().padStart(2, '0')
  return `${weekday} ${day}.${month}`
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

export default function ScanMode({ region, profile }) {
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

  function handleClubNameChange(val) {
    setClubName(val)
    setClubSlug('')
    setClubOptions([])
    if (clubDebounceRef.current) clearTimeout(clubDebounceRef.current)
    if (val.length < 2) return
    clubDebounceRef.current = setTimeout(async () => {
      setClubSearching(true)
      try {
        const res = await fetch(`${API_BASE}/api/clubs?q=${encodeURIComponent(val)}`)
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
      setError(t('scanMode.club_not_selected'))
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

      const res = await fetch(`${API_BASE}/api/search`, {
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
    <div className="scan-container">
      <form className="scan-form" onSubmit={handleSearch}>
        {/* Club search autocomplete */}
        <div className="scan-field">
          <label>{t('scanMode.club_label')}</label>
          <div className="scan-club-wrap">
            <input
              type="text"
              value={clubName}
              onChange={(e) => handleClubNameChange(e.target.value)}
              onBlur={() => setTimeout(() => setClubOptions([]), 150)}
              placeholder={t('scanMode.club_placeholder')}
              autoComplete="off"
              className={clubSlug ? 'scan-club-confirmed' : ''}
            />
            {clubSearching && <span className="scan-club-spinner">{t('scanMode.club_searching')}</span>}
            {clubOptions.length > 0 && (
              <ul className="scan-club-dropdown">
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
        <div className="scan-field--row">
          <div className="scan-field">
            <label>{t('scanMode.date_from')}</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => handleDateFromChange(e.target.value)}
              required
            />
          </div>
          <div className="scan-field">
            <label>{t('scanMode.date_to')}</label>
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
        <div className="scan-field--row">
          <div className="scan-field">
            <label>{t('scanMode.duration')}</label>
            <select value={duration} onChange={(e) => setDuration(e.target.value)}>
              <option value="">{t('scanMode.any_duration')}</option>
              <option value="60">60 min</option>
              <option value="90">90 min</option>
              <option value="120">120 min</option>
            </select>
          </div>
          <div className="scan-field">
            <label>{t('scanMode.court_type')}</label>
            <select value={courtType} onChange={(e) => setCourtType(e.target.value)}>
              <option value="">{t('scanMode.any_court')}</option>
              <option value="SINGLE">{t('scanMode.single')}</option>
              <option value="DOUBLE">{t('scanMode.double')}</option>
            </select>
          </div>
        </div>

        {/* Time windows */}
        <div className="scan-field">
          <label>{t('scanMode.time_windows')}</label>
          {windows.map((w, idx) => (
            <div key={idx} className="scan-window">
              <div className="scan-window-days">
                {DAY_KEYS.map((day) => (
                  <button
                    key={day}
                    type="button"
                    className={`day-btn${w.days.includes(day) ? ' active' : ''}`}
                    onClick={() => toggleDay(idx, day)}
                  >
                    {t(`scanMode.days.${day}`)}
                  </button>
                ))}
              </div>
              <div className="scan-window-times">
                <span>{t('scanMode.from_time')}</span>
                <input
                  type="time"
                  value={w.start}
                  onChange={(e) => updateWindowTime(idx, 'start', e.target.value)}
                />
                <span>{t('scanMode.to_time')}</span>
                <input
                  type="time"
                  value={w.end}
                  onChange={(e) => updateWindowTime(idx, 'end', e.target.value)}
                />
                {windows.length > 1 && (
                  <button type="button" className="scan-remove-btn" onClick={() => removeWindow(idx)}>
                    {t('scanMode.remove_window')}
                  </button>
                )}
              </div>
            </div>
          ))}
          <button type="button" className="scan-add-btn" onClick={addWindow}>
            {t('scanMode.add_window')}
          </button>
        </div>

        <button type="submit" className="scan-submit" disabled={loading}>
          {loading ? t('scanMode.searching') : t('scanMode.search_btn')}
        </button>
      </form>

      {error && <div className="scan-error">{error}</div>}

      {results !== null && (
        <div className="scan-results">
          {summary && summary.count > 0 && (
            <p className="scan-summary">
              {t('scanMode.results_summary', { count: summary.count, days: summary.days })}
            </p>
          )}
          {results.length === 0 ? (
            <p className="scan-no-results">{t('scanMode.no_results')}</p>
          ) : (
            Object.entries(grouped).map(([date, slots]) => (
              <div key={date} className="scan-date-group">
                <div className="scan-date-label">{formatDayLabel(date, region?.language || i18n.language)}</div>
                {slots.map((slot, i) => (
                  <div key={i} className="scan-slot">
                    <span className="scan-slot-time">{slot.local_time}</span>
                    <span className="scan-slot-court">{slot.court}</span>
                    <span className="scan-slot-meta">{slot.duration} min</span>
                    <span className="scan-slot-price">{slot.price}</span>
                    <a
                      href={slot.booking_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="scan-book-btn"
                    >
                      {t('scanMode.book_btn')}
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
