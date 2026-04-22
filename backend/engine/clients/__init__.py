"""Clients — the ONLY allowed cross-process boundary from the engine.

``django_api`` is a typed HTTP client for talking to the Django service.
Do not import ``apps.*`` directly — go through this layer.
"""
