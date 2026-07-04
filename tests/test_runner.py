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
  workers: int = 1
  use_snapshot_cache: bool = True
  today: date = date(2026, 7, 4)
  downloads_dir: str = '/tmp/downloads'
  outputs_dir: str = '/tmp/outputs'


class RunnerTests(unittest.TestCase):
  def _import_runner_with_fake_catalog(self):
    fake_catalog = types.ModuleType('wuddlib.catalog')

    class FakeBrowserSessionPool:
      def __init__(self):
        self.close_calls = 0

      def close(self):
        self.close_calls += 1

    class FakeCatalogSearchBatch:
      instances = []

      def __init__(
        self,
        osver,
        release,
        arch,
        update_type,
        browser,
        foreground,
        use_snapshot_cache=True,
        prime_update_date=None,
        browser_pool_size=1,
        browser_session_pool=None,
      ):
        self.osver = osver
        self.release = release
        self.arch = arch
        self.update_type = update_type
        self.browser = browser
        self.foreground = foreground
        self.use_snapshot_cache = use_snapshot_cache
        self.prime_update_date = prime_update_date
        self.browser_pool_size = browser_pool_size
        self.browser_session_pool = browser_session_pool
        self.discover_calls = []
        self.finalize_calls = []
        self.close_calls = 0
        FakeCatalogSearchBatch.instances.append(self)

      def discover(self, update_date):
        self.discover_calls.append(update_date)
        return types.SimpleNamespace(
          searchresult=True,
          dl_info_dict={
            'osver': self.osver,
            'release': self.release,
            'arch': self.arch,
            'date': update_date,
            'title': 'title',
            'kb': 'KB1',
            'updateID': f'{self.osver}-{self.release}-{self.arch}-{self.update_type}-{update_date}',
            'files': [],
            'sha1': [],
          },
        )

      def finalize(self, wudd):
        self.finalize_calls.append(wudd.dl_info_dict['date'])
        return wudd

      def resolve(self, update_date):
        self.discover_calls.append(update_date)
        self.finalize_calls.append(update_date)
        return types.SimpleNamespace(
          searchresult=True,
          dl_info_dict={
            'osver': self.osver,
            'release': self.release,
            'arch': self.arch,
            'date': update_date,
            'title': 'title',
            'kb': 'KB1',
            'updateID': f'{self.osver}-{self.release}-{self.arch}-{self.update_type}-{update_date}',
            'files': [],
            'sha1': [],
          },
        )

      def close(self):
        self.close_calls += 1

    def create_browser_session_pool(browser, foreground, max_size=1):
      return FakeBrowserSessionPool()

    fake_catalog.CatalogSearchBatch = FakeCatalogSearchBatch
    fake_catalog.create_browser_session_pool = create_browser_session_pool

    with patch.dict(sys.modules, {'wuddlib.catalog': fake_catalog}):
      runner = importlib.import_module('wuddlib.runner')
      runner = importlib.reload(runner)

    return runner, FakeCatalogSearchBatch

  def test_run_uses_date_range_and_writes_outputs_for_each_update(self):
    runner, FakeCatalogSearchBatch = self._import_runner_with_fake_catalog()
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
    self.assertEqual(len(FakeCatalogSearchBatch.instances), 2)
    self.assertEqual([instance.prime_update_date for instance in FakeCatalogSearchBatch.instances], ['2026-05', '2026-05'])
    self.assertEqual([sorted(instance.discover_calls) for instance in FakeCatalogSearchBatch.instances], [['2026-05', '2026-06'], ['2026-05', '2026-06']])
    self.assertEqual([sorted(instance.finalize_calls) for instance in FakeCatalogSearchBatch.instances], [['2026-05', '2026-06'], ['2026-05', '2026-06']])
    self.assertEqual([instance.close_calls for instance in FakeCatalogSearchBatch.instances], [1, 1])
    print_wudd_mock.assert_called()
    self.assertEqual(save_wudd_mock.call_count, 4)
    self.assertEqual(download_wudd_mock.call_count, 4)

  def test_run_uses_latest_patch_tuesday_when_requested(self):
    runner, FakeCatalogSearchBatch = self._import_runner_with_fake_catalog()
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

    self.assertEqual(len(FakeCatalogSearchBatch.instances), 1)
    self.assertEqual(FakeCatalogSearchBatch.instances[0].prime_update_date, '2026-06')
    self.assertEqual(FakeCatalogSearchBatch.instances[0].discover_calls, ['2026-06'])
    self.assertEqual(FakeCatalogSearchBatch.instances[0].finalize_calls, ['2026-06'])
    self.assertEqual(FakeCatalogSearchBatch.instances[0].close_calls, 1)
