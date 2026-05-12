"""Geographic distance and routing utilities.

Pure functions in `haversine`/`bbox`; provider-backed functionality lives
behind the `IRoutingProvider` port (`ports.py`) with a Mapbox Matrix
implementation in `mapbox_adapter`. The orchestrating cache-aware service
is in `service`.
"""
