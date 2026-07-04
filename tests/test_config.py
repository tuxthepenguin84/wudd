import json
import tempfile
from datetime import date
from pathlib import Path
import unittest

from wuddlib.config import get_dates, latest_patch_tuesday, load_json_file


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

  def test_load_json_file_reads_valid_json(self):
    with tempfile.TemporaryDirectory() as tmp_dir:
      path = Path(tmp_dir) / 'osinfo.json'
      payload = {'10': {'releases': {'22H2': {}}}}
      path.write_text(json.dumps(payload), encoding='utf-8')

      result = load_json_file(path)

      self.assertEqual(result, payload)

