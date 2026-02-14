import React from 'react'
import { useTranslation } from 'react-i18next'

export default function ProfileSuggestion({ suggestions, onAccept, onDismiss, PROFILE_LABELS }) {
    const { t } = useTranslation()
    if (!suggestions || suggestions.length === 0) return null

    return (
        <div className="profile-suggestion">
            <div className="suggestion-header">
                {t('profile.save_prompt')}
            </div>
            <div className="suggestion-items">
                {suggestions.filter(s => s.key !== 'preferred_club_slug').map((s, i) => (
                    <div key={i} className="suggestion-item">
                        <span className="suggestion-label">{t(PROFILE_LABELS[s.key] || s.key)}:</span>
                        <span className="suggestion-value">{s.value}</span>
                    </div>
                ))}
            </div>
            <div className="suggestion-actions">
                <button className="suggestion-accept" onClick={onAccept}>
                    {t('profile.save_btn')}
                </button>
                <button className="suggestion-dismiss" onClick={onDismiss}>
                    {t('profile.dismiss_btn')}
                </button>
            </div>
        </div>
    )
}
