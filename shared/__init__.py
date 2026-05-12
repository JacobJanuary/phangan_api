"""
Shared kernel — cross-feature reusable components.

Each subpackage exposes:
- `ports.py`  — abstract interfaces (typing.Protocol)
- adapters    — concrete implementations
- `service.py` — orchestration on top of ports

Features depend on the ports, never on adapters directly. This lets us
swap an in-memory implementation for Redis, a stub LLM for a real one,
etc., without touching feature code.
"""
