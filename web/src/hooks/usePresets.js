import { useState, useEffect } from 'react'

const STORAGE_KEY = 'padel-agent-scanner-presets'
const MAX_PRESETS = 10

export default function usePresets() {
    const [presets, setPresets] = useState(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY)
            return stored ? JSON.parse(stored) : []
        } catch {
            return []
        }
    })

    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(presets))
    }, [presets])

    function savePreset(name, settings) {
        if (!name.trim()) return

        const newPreset = {
            id: Date.now().toString(),
            name: name.trim(),
            settings,
        }

        setPresets((prev) => {
            // Remove any existing preset with exactly the same name to overwrite it
            const next = [newPreset, ...prev.filter((p) => p.name !== newPreset.name)]
            return next.slice(0, MAX_PRESETS)
        })
    }

    function deletePreset(id) {
        setPresets((prev) => prev.filter((p) => p.id !== id))
    }

    return { presets, savePreset, deletePreset }
}
