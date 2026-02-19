from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

OrderCallable = Callable[[int, list[dict[str, Any]]], tuple[list[dict[str, Any]], dict[str, Any]]]


def chunk_rows(rows: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    """Split rows into deterministic chunks for bulk orders."""
    size = max(int(chunk_size or 1), 1)
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def execute_bulk_orders(
    *,
    rows: list[dict[str, Any]],
    chunk_size: int,
    max_workers: int,
    order_callable: OrderCallable,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute order_callable asynchronously for each chunk and merge ordered results."""
    chunks = chunk_rows(rows, chunk_size)
    merged_rows: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(max_workers, 1)) as pool:
        futures = {
            pool.submit(order_callable, order_index, chunk): order_index
            for order_index, chunk in enumerate(chunks, start=1)
        }
        for future in as_completed(futures):
            order_index = futures[future]
            order_rows, summary = future.result()
            merged_rows.extend(order_rows)
            orders.append({'order_index': order_index, **summary})

    merged_rows.sort(key=lambda item: item.get('row_index', 0))
    orders.sort(key=lambda item: item['order_index'])
    return orders, merged_rows
