import hashlib
import json
import math
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import (MetaData, Table, Column, String, Integer, Date, Numeric,
                        ForeignKey, CheckConstraint, Index, select, insert, update, delete, func)


metadata = MetaData()
batches = Table('wh_batches', metadata,
    Column('batch_id', String(64), primary_key=True), Column('snapshot_id', String(64), nullable=False),
    Column('committed_at', String(40), nullable=False), Column('receipt', String, nullable=False))
state = Table('wh_state', metadata, Column('name', String(20), primary_key=True),
    Column('batch_id', String(64), ForeignKey('wh_batches.batch_id'), nullable=False))
categories = Table('wh_categories', metadata,
    Column('category_id', Integer, primary_key=True), Column('name', String(200), nullable=False))
suppliers = Table('wh_suppliers', metadata,
    Column('supplier_id', Integer, primary_key=True), Column('category_id', Integer, ForeignKey('wh_categories.category_id'), nullable=False),
    Column('canonical_name', String(200), nullable=False))
orders = Table('wh_purchase_orders', metadata,
    Column('po_line_id', String(80), primary_key=True),
    Column('supplier_id', Integer, ForeignKey('wh_suppliers.supplier_id'), nullable=False),
    Column('category_id', Integer, ForeignKey('wh_categories.category_id'), nullable=False),
    Column('order_date', Date, nullable=False), Column('quantity', Integer, nullable=False),
    Column('unit_price_usd', Numeric(20, 8), nullable=False), Column('extended_spend_usd', Numeric(22, 6), nullable=False),
    Column('off_contract_flag', Integer, nullable=False), Column('source_hash', String(64), nullable=False),
    Column('batch_id', String(64), ForeignKey('wh_batches.batch_id'), nullable=False),
    CheckConstraint('quantity > 0'), CheckConstraint('unit_price_usd > 0'),
    CheckConstraint('extended_spend_usd > 0'), CheckConstraint('off_contract_flag IN (0,1)'))
Index('wh_orders_category_date', orders.c.category_id, orders.c.order_date)
Index('wh_orders_supplier_date', orders.c.supplier_id, orders.c.order_date)
changes = Table('wh_changes', metadata,
    Column('change_id', Integer, primary_key=True, autoincrement=True),
    Column('batch_id', String(64), ForeignKey('wh_batches.batch_id'), nullable=False),
    Column('po_line_id', String(80), nullable=False), Column('operation', String(6), nullable=False),
    Column('before_json', String), Column('after_json', String),
    CheckConstraint("operation IN ('insert','update','delete')"))
Index('wh_changes_batch', changes.c.batch_id)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalized_orders(frame):
    required = ['po_line_id', 'supplier_id', 'category_id', 'order_date', 'quantity',
                'unit_price_usd', 'extended_spend_usd', 'off_contract_flag']
    result = []
    for row in frame[required].to_dict('records'):
        quantity = row['quantity']
        if not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity <= 0 or int(quantity) != quantity:
            raise ValueError('Warehouse quantities must be positive integers')
        for key, places in [('unit_price_usd', '0.00000001'), ('extended_spend_usd', '0.000001')]:
            value = Decimal(str(row[key]))
            if not value.is_finite() or value <= 0:
                raise ValueError('Warehouse monetary values must be positive and finite')
            row[key] = value.quantize(Decimal(places))
        row.update(po_line_id=str(row['po_line_id']), supplier_id=int(row['supplier_id']),
                   category_id=int(row['category_id']), quantity=int(quantity),
                   order_date=date.fromisoformat(str(row['order_date'])[:10]), off_contract_flag=int(row['off_contract_flag']))
        if abs(row['quantity'] * row['unit_price_usd'] - row['extended_spend_usd']) > Decimal('.001'):
            raise ValueError('Warehouse quantity/price/spend reconciliation failed')
        row['source_hash'] = digest(row)
        result.append(row)
    if len({r['po_line_id'] for r in result}) != len(result):
        raise ValueError('Duplicate purchase-order key blocks the complete snapshot')
    return sorted(result, key=lambda r: r['po_line_id'])


def write_lake(rows, batch_id, root):
    target = Path(root) / batch_id
    target.mkdir(parents=True, exist_ok=True)
    partitions = {}
    for row in rows:
        partitions.setdefault(row['order_date'].strftime('%Y-%m'), []).append(row)
    files = []
    for month, values in sorted(partitions.items()):
        path = target / ('month=' + month) / 'part-00000.parquet'
        path.parent.mkdir(exist_ok=True)
        table = pa.Table.from_pylist(values)
        payload = pa.BufferOutputStream()
        pq.write_table(table, payload, compression='zstd')
        content = payload.getvalue().to_pybytes()
        if path.exists() and path.read_bytes() != content:
            raise ValueError('Immutable lake partition differs from its published bytes')
        path.write_bytes(content)
        files.append(dict(path=path.relative_to(target).as_posix(), sha256=hashlib.sha256(content).hexdigest(),
                          rows=len(values), bytes=len(content)))
    manifest = dict(batch_id=batch_id, format='parquet', compression='zstd', partition_by='order month', files=files)
    (target / 'manifest.json').write_text(canonical(manifest), encoding='utf-8')
    return manifest


def publish_warehouse(frame, supplier_frame, category_frame, snapshot_id, lake_root, conn):
    metadata.create_all(conn)
    if conn.dialect.name == 'postgresql':
        conn.exec_driver_sql('SELECT pg_advisory_xact_lock(3790360)')
    rows = normalized_orders(frame)
    dims = dict(categories=category_frame[['category_id', 'name']].to_dict('records'),
                suppliers=supplier_frame[['supplier_id', 'category_id', 'canonical_name']].to_dict('records'))
    lookup = {int(s['supplier_id']): int(s['category_id']) for s in dims['suppliers']}
    if any(lookup.get(r['supplier_id']) != r['category_id'] for r in rows):
        raise ValueError('Purchase-order supplier/category join is invalid')
    batch_id = digest(dict(snapshot=snapshot_id, row_hashes=[r['source_hash'] for r in rows], dimensions=dims))
    prior = conn.execute(select(batches.c.receipt).where(batches.c.batch_id == batch_id)).scalar()
    if prior:
        current = conn.execute(select(state.c.batch_id).where(state.c.name == 'current')).scalar()
        if current != batch_id:
            raise ValueError('A superseded snapshot cannot replace current state; publish a new source revision')
        return {**json.loads(prior), 'replayed': True}
    lake = write_lake(rows, batch_id, lake_root)
    previous = {r['po_line_id']: dict(r) for r in conn.execute(select(orders)).mappings()}
    incoming = {r['po_line_id']: r for r in rows}
    added = [r for key, r in incoming.items() if key not in previous]
    revised = [r for key, r in incoming.items() if key in previous and r['source_hash'] != previous[key]['source_hash']]
    removed = [r for key, r in previous.items() if key not in incoming]
    receipt = dict(batch_id=batch_id, input_snapshot_id=snapshot_id, synthetic=True, rows=len(rows),
        inserted=len(added), updated=len(revised), deleted=len(removed), unchanged=len(rows)-len(added)-len(revised),
        total_spend_usd=str(sum((r['extended_spend_usd'] for r in rows), Decimal(0))),
        lake_partitions=len(lake['files']), lake_bytes=sum(f['bytes'] for f in lake['files']),
        lake_manifest_sha256=hashlib.sha256(canonical(lake).encode()).hexdigest(), replayed=False,
        storage=conn.dialect.name, transaction_scope='Dimensions, facts, correction/deletion log and publication receipt',
        deletion_policy='Full-source snapshots only: absent purchase-order keys produce explicit deletion log entries')
    conn.execute(insert(batches).values(batch_id=batch_id, snapshot_id=snapshot_id,
                 committed_at=datetime.now(timezone.utc).isoformat(), receipt=canonical(receipt)))
    for table, values, key in [(categories, dims['categories'], 'category_id'), (suppliers, dims['suppliers'], 'supplier_id')]:
        known = set(conn.execute(select(table.c[key])).scalars())
        for value in values:
            if value[key] in known:
                conn.execute(update(table).where(table.c[key] == value[key]).values(**value))
            else:
                conn.execute(insert(table).values(**value))
    for offset in range(0, len(added), 2000):
        conn.execute(insert(orders), [{**r, 'batch_id': batch_id} for r in added[offset:offset+2000]])
    for row in revised:
        conn.execute(update(orders).where(orders.c.po_line_id == row['po_line_id']).values(**row, batch_id=batch_id))
    for row in removed:
        conn.execute(delete(orders).where(orders.c.po_line_id == row['po_line_id']))
    history = [dict(batch_id=batch_id, po_line_id=r['po_line_id'], operation=op,
                    before_json=canonical(previous[r['po_line_id']]) if op != 'insert' else None,
                    after_json=canonical(r) if op != 'delete' else None)
               for op, records in [('insert', added), ('update', revised), ('delete', removed)] for r in records]
    for offset in range(0, len(history), 2000):
        conn.execute(insert(changes), history[offset:offset+2000])
    actual = conn.execute(select(func.count(), func.sum(orders.c.extended_spend_usd))).one()
    if actual[0] != len(rows) or abs((actual[1] or Decimal(0)) - Decimal(receipt['total_spend_usd'])) > Decimal('.01'):
        raise ValueError('Warehouse publication reconciliation failed')
    conn.execute(delete(state).where(state.c.name == 'current'))
    conn.execute(insert(state).values(name='current', batch_id=batch_id))
    return receipt


def verify_lake(root, batch_id):
    if len(batch_id) != 64 or any(c not in '0123456789abcdef' for c in batch_id):
        raise ValueError('Invalid lake snapshot ID')
    target = Path(root) / batch_id
    manifest = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
    result = []
    for entry in manifest['files']:
        path = target / entry['path']
        if not path.resolve().is_relative_to(target.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Lake partition checksum mismatch')
        table = pq.ParquetFile(path).read()
        if table.num_rows != entry['rows']:
            raise ValueError('Lake partition row count mismatch')
        result.extend(table.to_pylist())
    return result
