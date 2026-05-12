"""AI provider abstraction and cascade orchestrator.

Hides vendor-specific SDKs (Anthropic, OpenAI-compatible) behind a single
`IAIProvider` port. The `CascadeOrchestrator` retries within a single provider
and falls back to the next provider on terminal failure — used by features
like Vibe Pilot and gender inference.
"""
