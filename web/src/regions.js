/**
 * Region configuration for the Padel Agent.
 * Add new regions here to expand the selector.
 */
export const REGIONS = [
    { id: 'global', label: '🌍 Global', language: 'en', country: null, timezone: 'UTC' },
    { id: 'de', label: '🇩🇪 Germany', language: 'de', country: 'DE', timezone: 'Europe/Berlin' },
]

export const DEFAULT_REGION_ID = 'de'

export function getRegionById(id) {
    return REGIONS.find((r) => r.id === id) || REGIONS.find((r) => r.id === DEFAULT_REGION_ID)
}
