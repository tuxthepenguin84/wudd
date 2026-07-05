#!/usr/bin/env python3

import argparse
import sys
import time
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from wuddlib import catalog
from wuddlib import runner
from wuddlib.config import get_dates, load_data_file, resolve_year_month


def _build_parser():
  parser = argparse.ArgumentParser(description='Benchmark wudd worker counts on a representative live sample')
  parser.add_argument('--browser', default='chrome', choices=['chrome', 'firefox'])
  parser.add_argument('--workers', type=int, required=True)
  parser.add_argument('--months', type=int, default=12)
  parser.add_argument('--update-types', nargs='*')
  return parser


def _year_month_dict(year_month):
  year, month = year_month.split('-')
  return {'year': int(year), 'month': int(month)}


def main():
  args = _build_parser().parse_args()
  osinfo = load_data_file(REPO_ROOT / 'osinfo.toml')

  osver = next(iter(osinfo))
  release = next(iter(osinfo[osver]['releases']))
  arch = next(iter(osinfo[osver]['releases'][release]['archs']))
  arch_details = osinfo[osver]['releases'][release]['archs'][arch]

  date_range = get_dates(
    resolve_year_month(arch_details['start']),
    resolve_year_month(arch_details['end']),
  )
  if args.months > 0:
    date_range = date_range[-args.months:]
  if not date_range:
    raise SystemExit('No benchmark dates were available')

  update_types = args.update_types or list(arch_details.get('ut', []))
  if not update_types:
    raise SystemExit('No benchmark update types were available')

  sample_os_json = {
    osver: {
      'releases': {
        release: {
          'archs': {
            arch: {
              'ut': update_types,
              'start': _year_month_dict(date_range[0]),
              'end': _year_month_dict(date_range[-1]),
            }
          }
        }
      }
    }
  }

  def clear_caches():
    catalog._clear_search_index_cache()
    catalog._load_snapshot_file.cache_clear()
    catalog._lookup_snapshot_result.cache_clear()
    catalog._lookup_kb_hint.cache_clear()

  with tempfile.TemporaryDirectory(prefix='wudd-bench-downloads-') as downloads_dir, \
      tempfile.TemporaryDirectory(prefix='wudd-bench-outputs-') as outputs_dir:
    config = SimpleNamespace(
      browser=args.browser,
      clean=False,
      download=False,
      downloads_dir=downloads_dir,
      foreground=False,
      latest=False,
      outputs_dir=outputs_dir,
      skipsha1=False,
      today=None,
      use_snapshot_cache=False,
      workers=args.workers,
    )

    clear_caches()
    start = time.perf_counter()
    runner.run(sample_os_json, config)
    elapsed = time.perf_counter() - start

  print(
    f'workers={args.workers} months={len(date_range)} '
    f'update_types={len(update_types)} elapsed={elapsed:.2f}s'
  )


if __name__ == '__main__':
  main()
