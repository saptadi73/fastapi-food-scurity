"""Rolling UTC partition maintenance; no retention deletion or evidence mutation."""
import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database.partitions import month_range, partition_report
from app.core.database.session import close_database, get_admin_engine


async def run(args):
    first = args.start or datetime.now(UTC).date().replace(day=1)
    try:
        month_range(first, args.months)
        async with get_admin_engine().connect() as connection, connection.begin() as transaction:
            await connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            await connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            if args.ensure:
                await connection.execute(text('SELECT public.fsos_create_telemetry_partitions(:start, :months)'),
                                         {'start': first, 'months': args.months})
            report = await partition_report(connection, first, args.months)
            if args.ensure and not report['ready']:
                await transaction.rollback()
        report['mode'] = 'ensure' if args.ensure else 'check'
        code = 0 if report['ready'] else 2
    except Exception as exc:  # noqa: BLE001 - never print connection credentials
        report = {'ready': False, 'error_type': type(exc).__name__}
        code = 1
    finally:
        await close_database()
    report['checked_at'] = datetime.now(UTC).isoformat()
    output = json.dumps(report, indent=2)
    if args.report_file:
        args.report_file.parent.mkdir(parents=True, exist_ok=True)
        args.report_file.write_text(output + '\n', encoding='utf-8')
    if sys.stdout is not None:
        print(output)
    return code


def parse_month(value):
    try:
        if len(value) != 7:
            raise ValueError
        return date.fromisoformat(value + '-01')
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Use YYYY-MM') from exc


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--ensure', action='store_true')
    parser.add_argument('--start', type=parse_month, help='YYYY-MM; default current UTC month')
    parser.add_argument('--months', type=int, choices=range(1, 25), default=6)
    parser.add_argument('--report-file', type=Path)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
