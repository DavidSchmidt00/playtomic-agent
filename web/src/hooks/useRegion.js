import { useState, useCallback } from 'react'
import { getRegionById, DEFAULT_REGION_ID } from '../regions'

const STORAGE_KEY = 'padel_region'

export default function useRegion() {
    const [regionId, setRegionIdState] = useState(() => {
        try {
            return localStorage.getItem(STORAGE_KEY) || DEFAULT_REGION_ID
        } catch {
            return DEFAULT_REGION_ID
        }
    })

    const setRegionId = useCallback((id) => {
        setRegionIdState(id)
        try {
            localStorage.setItem(STORAGE_KEY, id)
        } catch {
            // localStorage not available
        }
    }, [])

    const region = getRegionById(regionId)

    return { region, setRegionId }
}
