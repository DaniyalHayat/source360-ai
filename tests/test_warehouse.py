import json
import os

import pandas as pd
import pytest
from sqlalchemy import create_engine, select, func, event

from source360.warehouse import publish_warehouse, verify_lake, orders, changes, state, batches, metadata


@pytest.fixture
def fixture(tmp_path):
    url = os.getenv('SOURCE360_TEST_WAREHOUSE_URL', 'sqlite:///' + str(tmp_path / 'warehouse.db'))
    db = create_engine(url)
    if db.dialect.name == 'postgresql':
        if not db.url.database.endswith('_warehouse_test'):
            raise ValueError('Use an isolated database ending in _warehouse_test')
        metadata.drop_all(db)
    else:
        with db.connect() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
    metadata.create_all(db)
    supplier = pd.DataFrame([dict(supplier_id=1, category_id=1, canonical_name='Supplier')])
    category = pd.DataFrame([dict(category_id=1, name='Category')])
    rows = pd.DataFrame([dict(po_line_id=str(i), supplier_id=1, category_id=1, order_date='2026-10-01',
        quantity=2, unit_price_usd=10., extended_spend_usd=20., off_contract_flag=1) for i in [1,2]])
    def publish(frame=rows, snapshot='a'):
        with db.begin() as conn:
            return publish_warehouse(frame, supplier, category, snapshot, tmp_path / 'lake', conn)
    return db, rows, publish, tmp_path / 'lake'


def test_idempotent_snapshot_then_late_correction_and_deletion(fixture):
    db, rows, publish, lake = fixture
    initial = publish()
    assert initial['inserted'] == 2
    assert publish()['replayed']
    corrected = rows.iloc[:1].copy()
    corrected['unit_price_usd'], corrected['extended_spend_usd'] = 12., 24.
    receipt = publish(corrected, 'b')
    assert (receipt['updated'], receipt['deleted'], receipt['inserted']) == (1,1,0)
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(orders)).scalar() == 1
        history = conn.execute(select(changes).where(changes.c.operation == 'update')).mappings().one()
        assert float(json.loads(history['before_json'])['extended_spend_usd']) == 20.
        assert float(json.loads(history['after_json'])['extended_spend_usd']) == 24.
    assert len(verify_lake(lake, initial['batch_id'])) == 2
    assert float(verify_lake(lake, receipt['batch_id'])[0]['extended_spend_usd']) == 24.
    with pytest.raises(ValueError, match='superseded'):
        publish()


def test_duplicate_keys_and_invalid_joins_block_publication(fixture):
    db, rows, publish, lake = fixture
    with pytest.raises(ValueError, match='Duplicate'):
        publish(pd.concat([rows, rows]))
    invalid = rows.copy(); invalid['supplier_id'] = 999
    with pytest.raises(ValueError, match='join'):
        publish(invalid)
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(batches)).scalar() == 0


def test_mid_transaction_failure_keeps_previous_committed_state(fixture):
    db, rows, publish, lake = fixture
    original = publish()
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO wh_changes'):
            raise RuntimeError('simulated change-log failure')
    event.listen(db, 'before_cursor_execute', fail)
    corrected = rows.copy(); corrected['quantity'] = 3; corrected['extended_spend_usd'] = 30.
    with pytest.raises(RuntimeError, match='change-log'):
        publish(corrected, 'new')
    event.remove(db, 'before_cursor_execute', fail)
    with db.connect() as conn:
        assert conn.execute(select(state.c.batch_id)).scalar() == original['batch_id']
        assert conn.execute(select(func.sum(orders.c.extended_spend_usd))).scalar() == 40
        assert conn.execute(select(func.count()).select_from(batches)).scalar() == 1


def test_partition_corruption_is_detected(fixture):
    db, rows, publish, lake = fixture
    result = publish()
    path = next((lake / result['batch_id']).rglob('*.parquet'))
    path.write_bytes(path.read_bytes() + b'corrupted')
    with pytest.raises(ValueError, match='checksum'):
        verify_lake(lake, result['batch_id'])


def test_financial_bridge_rejects_mismatched_line_amount(fixture):
    db, rows, publish, lake = fixture
    invalid = rows.copy(); invalid.loc[0, 'extended_spend_usd'] = 23.
    with pytest.raises(ValueError, match='reconciliation'):
        publish(invalid)
