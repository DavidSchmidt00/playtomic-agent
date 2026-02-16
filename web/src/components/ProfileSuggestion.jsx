import React from 'react'
import { useTranslation } from 'react-i18next'

export default function ProfileSuggestion({ suggestions, onAccept, onDismiss, PROFILE_LABELS }) {
    const { t } = useTranslation()
    if (!suggestions || suggestions.length === 0) return null

    const visibleSuggestions = suggestions.filter(s => s.key !== 'preferred_club_slug')

    return (
        <div className="profile-suggestion">
            <div className="suggestion-content">
                {visibleSuggestions.map((s, i) => (
                    <span key={i} className="suggestion-item">
                        <span className="suggestion-label">{t(PROFILE_LABELS[s.key] || s.key)}:</span>
                        <span className="suggestion-value">{s.value}</span>
                    </span>
                ))}
            </div>
            <div className="suggestion-actions">
                <button className="suggestion-accept" onClick={onAccept}>
                    {t('profile.save_btn')}
                </button>
                <button className="suggestion-dismiss" onClick={onDismiss}>
                    ✕
                </button>
            </div>
        </div>
    )
}

