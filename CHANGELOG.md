# Changelog

## [Unreleased]

- Public event metadata contract
- API endpoint refinements

## 2026-05-13

### Added
- Public event metadata contract support

### Changed
- Hide no-time events from public API

## 2026-05-12

### Fixed
- Avoid duplicate webhook registration on multi-worker startup
- Sync production API state after DB contract fixes

## 2026-04-16

### Added
- Cascading language detection (Cyrillic check + language_code + more)
- Cascading gender detection (dictionary + emoji validation + morphology)

## 2026-04-06

### Added
- Testing and benchmarking scripts

### Changed
- Migrated VibePilot planner cascade to support Deepseek and true AI

### Fixed
- Deep cleanup of duplicates and obsolete scripts

## 2026-03-31

### Fixed
- Guard against invalid event_time format in upcoming time filters

## 2026-03-29

### Changed
- Replaced broken mediapipe with cv2 cascade for server face detection
- Migrated from Gemini to Kimi Code API via Anthropic SDK

### Fixed
- Corrected Kimi base URL for Anthropic SDK to prevent 404

## 2026-03-28

### Added
- Recurrent events generator with schema updates and UI support

### Fixed
- Include raw event_time in _build_event to prevent UI saving empty values

## 2026-03-27

### Added
- Google Maps URL support in events schema and endpoints

## 2026-03-19

### Added
- Facepile enrichment to my-vibe endpoint for Who's Going section
- All candidates to planner response for complete swap alternatives

## 2026-03-18

### Changed
- Upgraded gender detection model to Gemini 3.1 Flash Lite Preview

## 2026-03-17

### Added
- Telegram bot webhook handler for /start command with welcome flow

## 2026-03-10

### Added
- GET /api/v1/translations endpoint
- Full i18n rewrite (189 keys)
- 5 new i18n sections + 6 swipe_feed keys (112 total entries)

### Fixed
- Map current_mood to DB column 'mood' and support null reset

## 2026-03-09

### Added
- POST /events/{id}/image upload with Pillow processing

### Fixed
- Convert event_date string to date object for asyncpg
- Add missing get_settings import for image upload endpoint
- Resolve telegram_id for event ownership check

---

*This changelog is reconstructed from repository commit history.*
*The project started as an API layer and evolved into a comprehensive backend system.*
