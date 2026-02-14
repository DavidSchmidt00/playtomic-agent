import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'padel_profile'

const PROFILE_LABELS = {
    preferred_club_name: '🏟️ Club',
    preferred_club_slug: '🔗 Club Slug',
    preferred_city: '📍 City',
    court_type: '🎾 Court Type',
    duration: '⏱️ Duration',
    preferred_time: '🕐 Preferred Time',
}

export default function useProfile() {
    const [profile, setProfile] = useState(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY)
            return stored ? JSON.parse(stored) : {}
        } catch {
            return {}
        }
    })

    // Persist to localStorage whenever profile changes
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
    }, [profile])

    const updateProfile = useCallback((key, value) => {
        setProfile((prev) => ({ ...prev, [key]: value }))
    }, [])

    const removePreference = useCallback((key) => {
        setProfile((prev) => {
            const next = { ...prev }
            delete next[key]
            return next
        })
    }, [])

    const clearProfile = useCallback(() => {
        setProfile({})
    }, [])

    return { profile, updateProfile, removePreference, clearProfile, PROFILE_LABELS }
}
