"""Engine-side DB layer — SQLAlchemy async for worker-owned tables.

Django owns migrations. These models mirror the Django-side definitions
for tables the worker writes heavily (inform_exchanges, device_stats,
flow_records). A drift test keeps them in sync.
"""
