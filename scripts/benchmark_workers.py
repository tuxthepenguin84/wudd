#!/usr/bin/env python3

import argparse
import json
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from wuddlib import catalog
from wuddlib.config import get_dates


def _build_parser():
  parser = argparse.ArgumentParser(description='Benchmark wudd worker counts on a representative live sample')
  parser.add_argument('--browser', default='chrome', choices=['chrome', 'firefox'])
  parser.add_argument('--workers', type=int, required=True)
  parser.add_argument('--months', type=int, default=12)
  parser.add_argument('--update-type', default='cu')
  return parser


def _year_month_dict(year_month):
  year, month = year_month.split('-')
  return {'year': int(year), 'month': int(month)}


def main():
  args = _build_parser().parse_args()
  osinfo = json.loads((REPO_ROOT / 'osinfo.json').read_text(encoding='utf-8'))

  osver = next(iter(osinfo))
  release = next(iter(osinfo[osver]['releases']))
  arch = next(iter(osinfo[osver]['releases'][release]['archs']))
  arch_details = osinfo[osver]['releases'][release]['archs'][arch]

  date_range = get_dates(arch_details['start'], arch_details['end'])
  if args.months > 0:
    date_range = date_range[-args.months:]
  if not date_range:
    raise SystemExit('No benchmark dates were available')

  benchmark_start = _year_month_dict(date_range[0])
  benchmark_end = _year_month_dict(date_range[-1])

  catalog._clear_search_index_cache()
  catalog._load_snapshot_file.cache_clear()
  catalog._lookup_snapshot_result.cache_clear()
  catalog._lookup_kb_hint.cache_clear()

  def resolve(update_date):
    catalog._clear_search_index_cache()
    search = catalog._build_search_context(
      osver,
      release,
      arch,
      args.update_type,
      update_date,
      args.browser,
      False,
      use_snapshot_cache=False,
    )
    try:
      search._searchresult()
      return search.searchresult is not None
    finally:
      search.session.close()

  start = time.perf_counter()
  with ThreadPoolExecutor(max_workers=min(args.workers, len(date_range))) as executor:
    futures = [executor.submit(resolve, update_date) for update_date in date_range]
    for future in as_completed(futures):
      future.result()
  elapsed = time.perf_counter() - start
  print(f'workers={args.workers} months={len(date_range)} elapsed={elapsed:.2f}s')


if __name__ == '__main__':
  main()
