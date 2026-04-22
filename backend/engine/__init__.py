"""UVL device engine — asyncio worker process, independent of Django.

Entry point: ``python -m engine.main``. Do not import ``apps.*`` from this
package. The only cross-boundary channel is ``engine.clients.django_api``,
which speaks HTTP to the Django service.
"""
