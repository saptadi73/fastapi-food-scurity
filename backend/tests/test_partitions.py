import os
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.partitions import month_range, partition_report

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')


def test_calendar_months_cross_year_and_leap_year():
    assert month_range(date(2023, 12, 1), 3) == [date(2023, 12, 1), date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)]


@pytest.mark.parametrize('start,months', [(date(2026, 9, 2), 1), (date(2026, 9, 1), 0),
                                         (date(2026, 9, 1), 25), (date(2026, 9, 1), True)])
def test_invalid_month_window(start, months):
    with pytest.raises(ValueError):
        month_range(start, months)


@pytest.mark.skipif(not TEST_URL, reason='Migrated FSOS_TEST_DATABASE_URL required')
async def test_partition_coverage_bounds_and_guards():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            transaction = await c.begin()
            try:
                # Use a distant empty window independent of the initial migration partitions.
                first = date(2040, 12, 1)
                before = await partition_report(c, first, 3)
                assert not before['ready'] and len(before['issues']) == 12
                for _ in range(2):
                    await c.execute(text("SELECT public.fsos_create_telemetry_partitions(DATE '2040-12-01', 3)"))
                report = await partition_report(c, first, 3)
                assert report['ready'] and report['expected_partitions'] == 12
                async with c.begin_nested() as savepoint:
                    await c.execute(text('ALTER TABLE temperature_log_204012 DISABLE TRIGGER telemetry_no_truncate'))
                    broken = await partition_report(c, first, 3)
                    assert broken['issues'] == [{'table': 'temperature_log_204012', 'reason': 'missing_or_disabled_guard',
                                                  'trigger': 'telemetry_no_truncate'}]
                    await savepoint.rollback()
                await c.execute(text("CREATE TABLE temperature_log_204103 PARTITION OF temperature_log "
                                     "FOR VALUES FROM ('2041-04-01 00:00:00+00') TO ('2041-05-01 00:00:00+00')"))
                broken = await partition_report(c, date(2041, 3, 1), 1)
                assert {'table': 'temperature_log_204103', 'reason': 'unexpected_bounds'} in broken['issues']
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
