#!/usr/bin/env python3
"""Analyze git activity for the past 7 days."""

import subprocess
from datetime import datetime, timedelta

def get_stats_for_date(date_str):
    """Get git stats for a specific date."""
    cmd = [
        'git', 'log',
        f'--since={date_str} 00:00',
        f'--until={date_str} 23:59',
        '--no-merges',
        '--numstat',
        '--pretty=%H'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    commits = []
    adds = dels = 0

    for line in result.stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            adds += int(parts[0])
            dels += int(parts[1])
        elif len(parts) == 1 and len(parts[0]) == 40:  # SHA
            commits.append(parts[0])

    return len(set(commits)), adds, dels

def main():
    print("=" * 70)
    print("PAST 7 DAYS ACTIVITY BREAKDOWN")
    print("=" * 70)
    print()

    total_commits = 0
    total_adds = 0
    total_dels = 0
    active_days = 0

    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        day_name = date.strftime('%A')

        commits, adds, dels = get_stats_for_date(date_str)

        if commits > 0:
            active_days += 1
            total_commits += commits
            total_adds += adds
            total_dels += dels
            net = adds - dels

            print(f"{date_str} ({day_name})")
            print(f"  Commits: {commits}")
            print(f"  Lines: +{adds:,} -{dels:,} (net: {net:,})")
            print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Active days: {active_days}")
    print(f"Total commits: {total_commits}")
    print(f"Total lines added: {total_adds:,}")
    print(f"Total lines deleted: {total_dels:,}")
    print(f"Net lines: {(total_adds - total_dels):,}")
    print()

    if active_days > 0:
        print("PRODUCTIVITY METRICS:")
        print(f"  Average commits/day: {total_commits / active_days:.1f}")
        print(f"  Average lines/day: {(total_adds - total_dels) / active_days:,.0f}")
        print(f"  Average gross output/day: {total_adds / active_days:,.0f}")
        print()

        # Compare to manual estimate
        manual_estimate_days = 103
        manual_daily_output = 144  # ~14,878 / 103

        print("COMPARISON TO MANUAL POC ESTIMATE:")
        print(f"  Manual estimate: {manual_estimate_days} days @ {manual_daily_output} lines/day")
        actual_daily = (total_adds - total_dels) / active_days
        print(f"  Actual (AI-assisted): {active_days} days @ {actual_daily:,.0f} lines/day")
        print(f"  Time multiplier: {manual_estimate_days / active_days:.1f}x faster")
        print(f"  Output multiplier: {actual_daily / manual_daily_output:.1f}x higher")
        print()

        # Calculate "equivalent" work
        total_net = total_adds - total_dels
        equivalent_manual_days = total_net / manual_daily_output
        print(f"EQUIVALENT MANUAL EFFORT:")
        print(f"  Total net output: {total_net:,} lines")
        print(f"  Equivalent manual days: {equivalent_manual_days:.1f} days")
        print(f"  Actual days worked: {active_days}")
        print(f"  Productivity gain: {equivalent_manual_days / active_days:.1f}x")

if __name__ == '__main__':
    main()
