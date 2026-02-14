import React from 'react'

export default function ProfileSuggestion({ suggestions, onAccept, onDismiss }) {
    if (!suggestions || suggestions.length === 0) return null

    const LABELS = {
        preferred_club_name: 'Preferred Club',
        preferred_club_slug: 'Club Slug',
        preferred_city: 'City',
        court_type: 'Court Type',
        duration: 'Duration',
        preferred_time: 'Preferred Time',
    }

    return (
        <div className="profile-suggestion">
            <div className="suggestion-header">
                💡 Save these preferences?
            </div>
            <div className="suggestion-items">
                {suggestions.filter(s => s.key !== 'preferred_club_slug').map((s, i) => (
                    <div key={i} className="suggestion-item">
                        <span className="suggestion-label">{LABELS[s.key] || s.key}:</span>
                        <span className="suggestion-value">{s.value}</span>
                    </div>
                ))}
            </div>
            <div className="suggestion-actions">
                <button className="suggestion-accept" onClick={onAccept}>
                    ✅ Save
                </button>
                <button className="suggestion-dismiss" onClick={onDismiss}>
                    ❌ No thanks
                </button>
            </div>
        </div>
    )
}
