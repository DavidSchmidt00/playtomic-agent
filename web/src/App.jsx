import React, { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import Chat from './components/Chat'
import FindMode from './components/FindMode'
import VotePage from './components/VotePage'
import RegionSelector from './components/RegionSelector'
import useRegion from './hooks/useRegion'
import useProfile from './hooks/useProfile'

export default function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('padel-agent-theme') || 'dark'
  })
  const modeFromPath = () => {
    const p = window.location.pathname
    if (p === '/find') return 'find'
    if (p.startsWith('/vote/')) return 'vote'
    return 'chat'
  }
  const voteIdFromPath = () => {
    const m = window.location.pathname.match(/^\/vote\/([a-z0-9]{8})$/)
    return m ? m[1] : null
  }
  const [mode, setMode] = useState(modeFromPath)
  const [voteId, setVoteId] = useState(voteIdFromPath)

  // Sync URL ↔ mode
  useEffect(() => {
    const onPopState = () => { setMode(modeFromPath()); setVoteId(voteIdFromPath()) }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])
  const { region, setRegionId } = useRegion()
  const { profile } = useProfile()
  const { t, i18n } = useTranslation()
  const chatRef = useRef(null)

  // Sync language with region
  useEffect(() => {
    if (region?.language) {
      i18n.changeLanguage(region.language)
    }
  }, [region, i18n])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('padel-agent-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  return (
    <div className="app-root">
      <header className="app-header">
        <h1>
          <span className="header-icon">🎾</span>
          <span className="header-accent">Padel Agent</span>
        </h1>
        <div className="mode-toggle-bar">
          <button
            className={`mode-btn${mode === 'chat' ? ' active' : ''}`}
            onClick={() => { history.pushState(null, '', '/chat'); setMode('chat') }}
          >
            {t('findMode.mode_chat')}
          </button>
          <button
            className={`mode-btn${mode === 'find' ? ' active' : ''}`}
            onClick={() => { history.pushState(null, '', '/find'); setMode('find') }}
          >
            {t('findMode.mode_find')}
          </button>
        </div>
        <div className="header-controls">
          <RegionSelector region={region} onRegionChange={setRegionId} />
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            <span className="theme-toggle-thumb">
              {theme === 'dark' ? '🌙' : '☀️'}
            </span>
          </button>
        </div>
      </header>
      <main>
        <div style={{ display: mode === 'chat' ? 'contents' : 'none' }}>
          <Chat ref={chatRef} region={region} />
        </div>
        <div style={{ display: mode === 'find' ? 'contents' : 'none' }}>
          <FindMode region={region} profile={profile} />
        </div>
        <div style={{ display: mode === 'vote' ? 'contents' : 'none' }}>
          {voteId && <VotePage voteId={voteId} />}
        </div>
      </main>
    </div>
  )
}
