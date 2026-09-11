import re
from datetime import UTC, date, datetime

from sqlalchemy import text

TABLES = ('temperature_log', 'humidity_log', 'gps_log', 'heartbeat_log')


def month_range(start: date, months: int) -> list[date]:
    if start.day != 1 or type(months) is not int or not 1 <= months <= 24:
        raise ValueError('First day and 1..24 months required')
    result = []
    for offset in range(months + 1):
        year, month = divmod(start.year * 12 + start.month - 1 + offset, 12)
        result.append(date(year, month + 1, 1))
    return result


async def partition_report(connection, start: date, months: int) -> dict:
    boundaries = month_range(start, months)
    await connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    rows = (await connection.execute(text("""
        SELECT child.relname AS name, parent.relname AS parent,
               pg_get_expr(child.relpartbound, child.oid) AS bounds
        FROM pg_inherits i
        JOIN pg_class child ON child.oid=i.inhrelid
        JOIN pg_class parent ON parent.oid=i.inhparent
        JOIN pg_namespace cn ON cn.oid=child.relnamespace
        JOIN pg_namespace pn ON pn.oid=parent.relnamespace
        WHERE cn.nspname='public' AND pn.nspname='public' AND child.relispartition
          AND parent.relname IN ('temperature_log','humidity_log','gps_log','heartbeat_log')
    """))).mappings().all()
    parts = {row['name']: row for row in rows}
    guards = set((await connection.execute(text("""
        SELECT c.relname, t.tgname FROM pg_trigger t
        JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND t.tgenabled IN ('O','A')
          AND t.tgfoid=to_regprocedure('public.fsos_reject_telemetry_mutation()')
          AND ((t.tgname='telemetry_immutable' AND t.tgtype=27)
            OR (t.tgname='telemetry_no_truncate' AND t.tgtype=34))
    """))).all())
    issues = []
    expected = []
    for table in TABLES:
        for index, first in enumerate(boundaries[:-1]):
            name = f'{table}_{first:%Y%m}'
            expected.append(name)
            row = parts.get(name)
            if row is None:
                issues.append({'table': name, 'reason': 'missing_partition'})
                continue
            match = re.fullmatch(r"FOR VALUES FROM \('([^']+)'\) TO \('([^']+)'\)", row['bounds'] or '')
            valid = False
            if match:
                try:
                    actual = tuple(datetime.fromisoformat(value) for value in match.groups())
                    wanted = tuple(datetime(d.year, d.month, 1, tzinfo=UTC) for d in boundaries[index:index + 2])
                    valid = actual == wanted and row['parent'] == table
                except ValueError:
                    pass
            if not valid:
                issues.append({'table': name, 'reason': 'unexpected_bounds'})
        for target in (table, *(name for name in expected if name.startswith(table + '_'))):
            if target != table and target not in parts:
                continue
            for trigger in ('telemetry_immutable', 'telemetry_no_truncate'):
                if (target, trigger) not in guards:
                    issues.append({'table': target, 'reason': 'missing_or_disabled_guard', 'trigger': trigger})
    return {'ready': not issues, 'start': start.strftime('%Y-%m'), 'months': months,
            'expected_partitions': len(expected), 'issues': issues}
