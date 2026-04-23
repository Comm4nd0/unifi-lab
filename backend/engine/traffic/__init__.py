"""Traffic simulator — Phase 3 worker-side flow injection.

See ``ticker.py`` for the tick loop that reads active ``TrafficProfile``
rows and writes ``FlowRecord`` rows.
"""

from __future__ import annotations

from .ticker import TrafficTicker, run_ticker_loop

__all__ = ["TrafficTicker", "run_ticker_loop"]
