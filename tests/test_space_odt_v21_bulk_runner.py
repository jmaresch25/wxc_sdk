from __future__ import annotations

from Space_OdT.v21.transformacion.bulk_runner import chunk_rows, execute_bulk_orders


def test_chunk_rows_splits_consistently():
    rows = [{'id': str(i)} for i in range(5)]
    chunks = chunk_rows(rows, 2)
    assert [len(chunk) for chunk in chunks] == [2, 2, 1]


def test_execute_bulk_orders_merges_and_orders_results():
    rows = [{'id': str(i)} for i in range(4)]

    def _order_callable(order_index, chunk):
        payload = [
            {'row_index': ((order_index - 1) * 2) + offset, 'value': item['id']}
            for offset, item in enumerate(chunk, start=1)
        ]
        return payload, {'status': 'completed', 'rows_total': len(payload)}

    orders, merged = execute_bulk_orders(rows=rows, chunk_size=2, max_workers=2, order_callable=_order_callable)

    assert [order['order_index'] for order in orders] == [1, 2]
    assert [item['row_index'] for item in merged] == [1, 2, 3, 4]
