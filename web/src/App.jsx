import React, { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import Chat from './components/Chat'
import ScanMode from './components/ScanMode'
import RegionSelector from './components/RegionSelector'
import useRegion from './hooks/useRegion'
import useProfile from './hooks/useProfile'

export default function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('padel-agent-theme') || 'dark'
  })
  const [mode, setMode] = useState('chat')
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
      <div className="mode-toggle-bar">
        <button
          className={`mode-btn${mode === 'chat' ? ' active' : ''}`}
          onClick={() => setMode('chat')}
        >
          {t('scanMode.mode_chat')}
        </button>
        <button
          className={`mode-btn${mode === 'scan' ? ' active' : ''}`}
          onClick={() => setMode('scan')}
        >
          {t('scanMode.mode_scan')}
        </button>
      </div>
      <main>
        {mode === 'scan'
          ? <ScanMode region={region} profile={profile} />
          : <Chat ref={chatRef} region={region} />
        }
      </main>
    </div>
  )
}
