"""Users feature — profile + background enrichment workers.

Do NOT import `routes` eagerly here — keeping the package import light
lets pure unit tests (gender_detection, language_detection, avatar)
run without FastAPI installed.
"""
