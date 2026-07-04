import csv
import json
import tempfile
from pathlib import Path
import unittest

from wuddlib.outputs import dedupe_txt, json_struct, merge_dict, reset_files, save_wudd


class OutputsTests(unittest.TestCase):
  def setUp(self):
    self.sample_data = {
      'osver': '11',
      'release': '24H2',
      'arch': 'x64',
      'date': '2026-06',
      'title': '2026-06 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB9999999)',
      'kb': 'KB9999999',
      'updateID': '11111111-2222-3333-4444-555555555555',
      'files': ['https://example.com/windows11.0-kb9999999-x64_deadbeefcafebabe1234567890abcdef12345678.msu'],
      'sha1': ['deadbeefcafebabe1234567890abcdef12345678'],
    }

  def test_merge_dict_recursively_merges_nested_dicts(self):
    left = {'11': {'24H2': {'x64': {'2026-06': {'existing': {'title': 'old'}}}}}}
    right = {'11': {'24H2': {'x64': {'2026-06': {'new': {'title': 'new'}}}}}}

    result = merge_dict(left, right)

    self.assertEqual(result['11']['24H2']['x64']['2026-06']['existing']['title'], 'old')
    self.assertEqual(result['11']['24H2']['x64']['2026-06']['new']['title'], 'new')

  def test_json_struct_builds_expected_shape(self):
    result = json_struct(self.sample_data)

    self.assertEqual(result['11']['24H2']['x64']['2026-06'][self.sample_data['updateID']]['kb'], 'KB9999999')

  def test_dedupe_txt_removes_duplicate_lines_preserving_order(self):
    with tempfile.TemporaryDirectory() as tmp_dir:
      path = Path(tmp_dir) / 'sample.txt'
      path.write_text('header\nrow1\nrow1\nrow2\nrow2\n', encoding='utf-8')

      dedupe_txt(path)

      self.assertEqual(path.read_text(encoding='utf-8'), 'header\nrow1\nrow2\n')

  def test_reset_files_creates_expected_files(self):
    with tempfile.TemporaryDirectory() as tmp_dir:
      downloads_dir = Path(tmp_dir) / 'downloads'
      outputs_dir = Path(tmp_dir) / 'outputs'
      downloads_dir.mkdir()
      (downloads_dir / 'stale.bin').write_text('old data', encoding='utf-8')
      outputs_dir.mkdir()
      (outputs_dir / 'stale.txt').write_text('old data', encoding='utf-8')

      reset_files(str(downloads_dir), str(outputs_dir), clean=True, download=True)

      self.assertTrue(outputs_dir.is_dir())
      self.assertTrue((outputs_dir / 'wudd.csv').is_file())
      self.assertTrue((outputs_dir / 'wudd.json').is_file())
      self.assertTrue((outputs_dir / 'wudd.txt').is_file())
      self.assertFalse(downloads_dir.exists())

  def test_save_wudd_writes_outputs(self):
    with tempfile.TemporaryDirectory() as tmp_dir:
      downloads_dir = Path(tmp_dir) / 'downloads'
      outputs_dir = Path(tmp_dir) / 'outputs'

      reset_files(str(downloads_dir), str(outputs_dir), clean=True, download=False)
      save_wudd(self.sample_data, str(outputs_dir))
      save_wudd(self.sample_data, str(outputs_dir))

      csv_lines = (outputs_dir / 'wudd.csv').read_text(encoding='utf-8').splitlines()
      txt_lines = (outputs_dir / 'wudd.txt').read_text(encoding='utf-8').splitlines()
      json_data = json.loads((outputs_dir / 'wudd.json').read_text(encoding='utf-8'))

      self.assertEqual(len(csv_lines), 2)
      self.assertEqual(len(txt_lines), 2)
      self.assertIn('11', json_data)
      self.assertIn('24H2', json_data['11'])
      self.assertIn('x64', json_data['11']['24H2'])
      self.assertIn('2026-06', json_data['11']['24H2']['x64'])
      self.assertIn(self.sample_data['updateID'], json_data['11']['24H2']['x64']['2026-06'])

  def test_save_wudd_preserves_sorted_order_when_merging_existing_rows(self):
    with tempfile.TemporaryDirectory() as tmp_dir:
      downloads_dir = Path(tmp_dir) / 'downloads'
      outputs_dir = Path(tmp_dir) / 'outputs'

      reset_files(str(downloads_dir), str(outputs_dir), clean=True, download=False)

      existing = {
        '11': {
          '24H2': {
            'x64': {
              '2026-06': {
                'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee': {
                  'title': '2026-06 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB9999998)',
                  'kb': 'KB9999998',
                  'files': ['https://example.com/later.msu'],
                  'sha1': ['laterhash'],
                }
              }
            }
          }
        }
      }
      (outputs_dir / 'wudd.json').write_text(json.dumps(existing), encoding='utf-8')

      older_data = dict(self.sample_data)
      older_data.update({
        'date': '2025-12',
        'title': '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB8888888)',
        'kb': 'KB8888888',
        'updateID': 'ffffffff-eeee-dddd-cccc-bbbbbbbbbbbb',
        'files': ['https://example.com/older.msu'],
        'sha1': ['olderhash'],
      })

      save_wudd(older_data, str(outputs_dir))

      with (outputs_dir / 'wudd.csv').open(newline='', encoding='utf-8') as csv_file:
        rows = list(csv.DictReader(csv_file))

      self.assertEqual(rows[0]['date'], '2025-12')
      self.assertEqual(rows[0]['kb'], 'KB8888888')
      self.assertEqual(rows[1]['date'], '2026-06')
      self.assertEqual(rows[1]['kb'], 'KB9999998')
