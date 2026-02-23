import React, { useState, useRef, useEffect } from 'react'
import { REGIONS } from '../regions'

export default function RegionSelector({ region, onRegionChange }) {
    const [open, setOpen] = useState(false)
    const ref = useRef(null)

    // Close dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(e) {
            if (ref.current && !ref.current.contains(e.target)) {
                setOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    return (
        <div className="region-selector" ref={ref}>
            <button
                className="region-toggle"
                onClick={() => setOpen(!open)}
                aria-label="Select region"
                title={region.label}
            >
                {region.label.split(' ')[0]}
            </button>
            {open && (
                <div className="region-dropdown">
                    {REGIONS.map((r) => (
                        <button
                            key={r.id}
                            className={`region-option ${r.id === region.id ? 'active' : ''}`}
                            onClick={() => {
                                onRegionChange(r.id)
                                setOpen(false)
                            }}
                        >
                            {r.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}
