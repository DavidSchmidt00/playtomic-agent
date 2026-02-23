import React from 'react'
import { useTranslation } from 'react-i18next'

export default function ProfileCard({ profile, PROFILE_LABELS, onRemove, onClear }) {
    const { t } = useTranslation()
    const entries = Object.entries(profile).filter(
        ([key]) => key in PROFILE_LABELS && key !== 'preferred_club_slug'
    )

    if (entries.length === 0) return null

    return (
        <div className="profile-card">
            <div className="profile-header">
                <span className="profile-title">{t('profile.memory')}</span>
                <button
                    className="profile-clear"
                    onClick={onClear}
                    title={t('profile.clear')}
                >
                    ✕
                </button>
            </div>
            <div className="profile-items">
                {entries.map(([key, value]) => (
                    <div key={key} className="profile-item">
                        <span className="profile-label">{t(PROFILE_LABELS[key])}</span>
                        <span className="profile-value">{value}</span>
                        <button
                            className="profile-remove"
                            onClick={() => onRemove(key)}
                            title={t('profile.remove', { label: t(PROFILE_LABELS[key]) })}
                        >
                            ×
                        </button>
                    </div>
                ))}
            </div>
        </div>
    )
}
