import tempfile
from datetime import date
from pathlib import Path
import unittest

from wuddlib.config import get_dates, latest_patch_tuesday, load_data_file, resolve_year_month


class ConfigTests(unittest.TestCase):
  def test_get_dates_inclusive_range(self):
    result = get_dates({'year': 2024, 'month': 11}, {'year': 2025, 'month': 2})
    self.assertEqual(result, ['2024-11', '2024-12', '2025-01', '2025-02'])

  def test_latest_patch_tuesday_returns_previous_month_when_current_patch_day_is_future(self):
    result = latest_patch_tuesday(date(2026, 7, 4))
    self.assertEqual(result, ['2026-06'])

  def test_latest_patch_tuesday_returns_current_month_when_patch_day_has_passed(self):
    result = latest_patch_tuesday(date(2026, 7, 20))
    self.assertEqual(result, ['2026-07'])

  def test_load_data_file_reads_valid_toml(self):
    with tempfile.TemporaryDirectory() as tmp_dir:
      path = Path(tmp_dir) / 'osinfo.toml'
      payload = {
        '10': {
          'releases': {
            '22H2': {
              'archs': {
                'x64': {'ut': ['cu'], 'start': {'year': 2024, 'month': 1}, 'end': 'latest_patch_tuesday'},
                'arm64': {'ut': ['cu'], 'start': {'year': 2024, 'month': 1}, 'end': 'latest_patch_tuesday'},
              }
            },
            '23H2': {
              'archs': {
                'x64': {'ut': ['cu'], 'start': {'year': 2024, 'month': 2}, 'end': 'latest_patch_tuesday'},
                'arm64': {'ut': ['cu'], 'start': {'year': 2024, 'month': 2}, 'end': 'latest_patch_tuesday'},
              }
            },
          }
        }
      }
      path.write_text(
        '[[targets]]\n'
        'os = "10"\n'
        'archs = ["x64", "arm64"]\n'
        'updates = ["cu"]\n'
        '\n'
        '[targets.releases."22H2"]\n'
        'start = "2024-01"\n'
        'end = "latest_patch_tuesday"\n'
        '\n'
        '[targets.releases."23H2"]\n'
        'start = "2024-02"\n'
        'end = "latest_patch_tuesday"\n',
        encoding='utf-8',
      )

      result = load_data_file(path)

      self.assertEqual(result, payload)

  def test_resolve_year_month_expands_latest_patch_tuesday_keyword(self):
    result = resolve_year_month('latest_patch_tuesday', date(2026, 7, 4))
    self.assertEqual(result, {'year': 2026, 'month': 6})
