"""Standalone CLI script to seed realistic sample workouts or reset demo data.

Usage:
    python -m src.scripts.seed_demo          # Seeds demo athlete, philosophy, and workouts
    python -m src.scripts.seed_demo --reset  # Purges all sessions where is_demo=True
"""

import argparse
import asyncio
import sys

from src.core.database import async_session_factory
from src.services.seed_service import SeedService


async def main():
    parser = argparse.ArgumentParser(description="Seed or reset Coach3 demo workouts.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Purge all demo workout data (is_demo=True) while preserving real records.",
    )
    args = parser.parse_args()

    async with async_session_factory() as session:
        if args.reset:
            deleted = await SeedService.purge_demo_data(session)
            print(f"✓ Reset complete. Purged {deleted} demo workout records.")
        else:
            w_count, s_count = await SeedService.seed_sample_workouts(session)
            if w_count == 0 and s_count == 0:
                print("Notice: Demo workouts already exist in database. Use --reset first if you wish to re-seed.")
            else:
                print(f"✓ Seed complete! Created {w_count} multi-modal workouts and {s_count} strength sets.")


if __name__ == "__main__":
    asyncio.run(main())
