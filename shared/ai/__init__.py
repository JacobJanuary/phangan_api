"""AI provider abstraction and cascade orchestrator.

Hides the vendor SDK (Anthropic) behind a single
`IAIProvider` port. The `CascadeOrchestrator` retries within a single provider
and falls back to the next provider on terminal failure — used by features
like Vibe Pilot and gender inference.
"""
