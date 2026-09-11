"""Buat partisi bulanan tanpa mengubah atau menghapus bukti yang sudah ada."""
import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database.session import close_database, get_admin_engine


async def main(start: date, months: int):
    try:
        async with get_admin_engine().begin() as connection:
            await connection.execute(text("SELECT public.fsos_create_telemetry_partitions(:start, :months)"),
                                     {"start": start, "months": months})
        print(f"Partisi siap: {start:%Y-%m}, {months} bulan, empat tabel sensor (UTC).")
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Buat partisi sensor bulanan; tidak menghapus data.")
    parser.add_argument("--start", required=True, help="Bulan awal YYYY-MM")
    parser.add_argument("--months", type=int, default=3, choices=range(1, 25))
    args = parser.parse_args()
    try:
        first_day = date.fromisoformat(args.start + "-01")
    except ValueError:
        parser.error("--start harus YYYY-MM yang valid")
    asyncio.run(main(first_day, args.months))
