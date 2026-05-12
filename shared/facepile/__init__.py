"""Facepile selection — gender/mood-aware phantom avatar pickers.

Pure logic. The DB-backed repository (Postgres queries) and the orchestrating
service that ties caching + repository + selector together live in `repository`
and `service` (not yet wired by Phase 2 — added by Phase 3 alongside the
'who's going' feature slice).
"""
