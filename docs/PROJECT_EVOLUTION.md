# Project Evolution

## phangan_api (Swyby Backend)

### Overview

The backend API powering Swyby's activity recommendation system. Built with Python
and Flask, it handles everything from user authentication to AI-powered planning.

### Architecture

- **Framework:** Flask (Python 3.12)
- **Database:** PostgreSQL with asyncpg
- **AI Integration:** Multiple providers (Kimi via Anthropic SDK, Deepseek, Gemini)
- **Image Processing:** Pillow, OpenCV
- **Internationalization:** 189+ translation keys

### Development Timeline

#### March 2026 — Foundation and AI Integration

**Early March:**
- Initial API scaffolding with event CRUD operations
- Image upload endpoint with Pillow processing
- Database schema for events, venues, and users
- Telegram bot webhook integration

**Mid-March:**
- Full i18n system (189 keys, multiple languages)
- Gender detection pipeline with model upgrades
- Facepile enrichment for social features
- Google Maps integration for venue locations

**Late March:**
- Migration from Gemini to Kimi Code API
- Face detection with OpenCV cascade classifiers
- Recurrent events support
- VibePilot planner with Deepseek integration

#### April 2026 — Language and Refinement

- Cascading language detection (Cyrillic support)
- Cascading gender detection with emoji validation
- Deep cleanup of duplicate scripts
- Testing and benchmarking infrastructure

#### May 2026 — Production Hardening

- Public event metadata contracts
- Webhook duplicate prevention
- Production state synchronization
- API endpoint refinements

### Key Technical Decisions

1. **Multi-provider AI:** Supports Kimi, Deepseek, and Gemini for redundancy
2. **Async throughout:** asyncpg for database, async handlers for webhooks
3. **i18n first:** Built internationalization from day one
4. **Image pipeline:** Server-side processing with Pillow + OpenCV

---

*This project represents the backend backbone of Swyby, connecting the AI engine,*
*event aggregator, and mobile clients into a cohesive system.*
