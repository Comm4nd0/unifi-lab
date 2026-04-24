"""Project-wide DRF pagination classes.

``InformExchangeCursor`` — cursor-based pagination for the device inform log.
Cursors are opaque to callers (base64-encoded position tokens) so the log
can be polled efficiently without page-number drift as new exchanges arrive.

Usage in a ViewSet action:

    from apps.common.pagination import InformExchangeCursor

    paginator = InformExchangeCursor()
    page = paginator.paginate_queryset(qs, request, view=self)
    serializer = InformExchangeSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)
"""

from __future__ import annotations

from rest_framework.pagination import CursorPagination


class InformExchangeCursor(CursorPagination):
    """Cursor pagination for ``InformExchange`` records.

    Ordered newest-first (``-exchanged_at, -id``) so new exchanges appear at
    the front of the first page and the cursor advances through history.
    """

    page_size = 50
    ordering = ("-exchanged_at", "-id")
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"
    max_page_size = 200
