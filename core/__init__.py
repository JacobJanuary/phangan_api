"""
Core infrastructure layer.

Cross-cutting concerns shared by every feature:
- `config`: Pydantic settings + business constants
- `database`: asyncpg pool lifecycle
- `logging`: structured logging with request correlation
- `exceptions`: domain-level exception hierarchy
- `error_handlers`: maps domain exceptions to HTTP responses

This package must NOT import from `features/` or `shared/`.
It defines the foundation everything else builds on.
"""
