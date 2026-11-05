"""Optional `limit` / `offset` query parameters and the `X-Total-Count` response header for list endpoints that can grow.

Defaults (limit 200, offset 0) reproduce the unpaginated behaviour for fewer than 200 rows. When the page is not full and
offset is 0 the total is simply the row count, so the common case costs no extra query."""
from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Query, Response

DEFAULT_LIMIT = 200
MAX_LIMIT = 500

Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Page size (default 200, max 500)")]
Offset = Annotated[int, Query(ge=0, le=1_000_000, description="Rows to skip")]


def set_total(response: Response, rows_returned: int, limit: int, offset: int, count: Callable[[], int]) -> int:
    """Set X-Total-Count. `count` is only called when the page cannot tell the total by itself."""
    total = rows_returned if (offset == 0 and rows_returned < limit) else int(count())
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return total
