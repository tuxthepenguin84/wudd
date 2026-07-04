import importlib
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import date
from unittest.mock import Mock, patch


@dataclass
class DummyConfig:
  browser: str = 'chrome'
  clean: bool = False
  download: bool = False
  foreground: bool = False
  latest: bool = False
  skipsha1: bool = False
  today: date = date(2026, 7, 4)
  downloads_dir: str = '/tmp/downloads'
  outputs_dir: str = '/tmp/outputs'


class RunnerTests(unittest.TestCase):
  def _import_runner_with_fake_catalog(self):
    fake_catalog = types.ModuleType('wuddlib.catalog')

    class FakeCatalogSearch:
      instances = []

      def __init__(self, osver, release, arch, update_type, update_date, browser, foreground):
        self.osver = osver
        self.release = release
        self.arch = arch
        self.update_type = update_type
        self.update_date = update_date
        self.browser = browser
        self.foreground = foreground
        self.searchresult = True
        self.dl_info_dict = {
          'osver': osver,
          'release': release,
          'arch': arch,
          'date': update_date,
          'title': 'title',
          'kb': 'KB1',
          'updateID': f'{osver}-{release}-{arch}-{update_type}-{update_date}',
          'files': [],
          'sha1': [],
        }
        FakeCatalogSearch.instances.append(self)

    fake_catalog.CatalogSearch = FakeCatalogSearch

    with patch.dict(sys.modules, {'wuddlib.catalog': fake_catalog}):
      runner = importlib.import_module('wuddlib.runner')
      runner = importlib.reload(runner)

    return runner, FakeCatalogSearch

  def test_run_uses_date_range_and_writes_outputs_for_each_update(self):
    runner, FakeCatalogSearch = self._import_runner_with_fake_catalog()
    config = DummyConfig(latest=False, download=True)
    os_json = {
      '10': {
        'releases': {
          '22H2': {
            'archs': {
              'x64': {
                'ut': ['cu', 'dcu'],
                'start': {'year': 2026, 'month': 5},
                'end': {'year': 2026, 'month': 6},
              }
            }
          }
        }
      }
    }

    with patch.object(runner, 'reset_files') as reset_files_mock, \
        patch.object(runner, 'print_wudd') as print_wudd_mock, \
        patch.object(runner, 'save_wudd') as save_wudd_mock, \
        patch.object(runner, 'download_wudd') as download_wudd_mock:
      runner.run(os_json, config)

    reset_files_mock.assert_called_once_with(config.downloads_dir, config.outputs_dir, config.clean, config.download)
    self.assertEqual(len(FakeCatalogSearch.instances), 4)
    self.assertEqual([instance.update_date for instance in FakeCatalogSearch.instances], ['2026-05', '2026-06', '2026-05', '2026-06'])
    print_wudd_mock.assert_called()
    self.assertEqual(save_wudd_mock.call_count, 4)
    self.assertEqual(download_wudd_mock.call_count, 4)

  def test_run_uses_latest_patch_tuesday_when_requested(self):
    runner, FakeCatalogSearch = self._import_runner_with_fake_catalog()
    config = DummyConfig(latest=True, download=False)
    os_json = {
      '11': {
        'releases': {
          '24H2': {
            'archs': {
              'x64': {
                'ut': ['cu'],
                'start': {'year': 2026, 'month': 1},
                'end': {'year': 2026, 'month': 6},
              }
            }
          }
        }
      }
    }

    with patch.object(runner, 'reset_files'), \
        patch.object(runner, 'print_wudd'), \
        patch.object(runner, 'save_wudd'), \
        patch.object(runner, 'download_wudd'):
      runner.run(os_json, config)

    self.assertEqual(len(FakeCatalogSearch.instances), 1)
    self.assertEqual(FakeCatalogSearch.instances[0].update_date, '2026-06')

