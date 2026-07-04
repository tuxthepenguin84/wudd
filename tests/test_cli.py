import contextlib
import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class CliTests(unittest.TestCase):
  def test_build_parser_defaults(self):
    import wudd

    args = wudd.build_parser().parse_args([])

    self.assertEqual(args.browser, 'chrome')
    self.assertFalse(args.clean)
    self.assertFalse(args.download)
    self.assertFalse(args.foreground)
    self.assertFalse(args.latest)
    self.assertEqual(args.logging, 'info')
    self.assertFalse(args.skipsha1)
    self.assertEqual(args.workers, 4)
    self.assertTrue(args.use_snapshot_cache)

  def test_build_parser_help_shows_defaults(self):
    import wudd

    help_text = wudd.build_parser().format_help()

    self.assertIn('--workers WORKERS', help_text)
    self.assertIn('Parallel lookup workers (default: 4)', help_text)

  def test_main_loads_config_and_invokes_runner(self):
    import wudd

    fake_runner = types.ModuleType('wuddlib.runner')
    fake_runner.run = Mock()

    with tempfile.TemporaryDirectory() as tmp_dir:
      osinfo_path = Path(tmp_dir) / 'osinfo.json'
      osinfo_path.write_text('{"10": {"releases": {}}}', encoding='utf-8')

      fake_config = Mock()
      fake_config.browser = 'firefox'
      fake_config.clean = True
      fake_config.download = True
      fake_config.foreground = True
      fake_config.latest = True
      fake_config.log_level = 'debug'
      fake_config.skipsha1 = True
      fake_config.workers = 4
      fake_config.use_snapshot_cache = False
      fake_config.local_dir = tmp_dir
      fake_config.downloads_dir = str(Path(tmp_dir) / 'downloads')
      fake_config.outputs_dir = str(Path(tmp_dir) / 'outputs')

      with patch.object(wudd, 'build_parser') as build_parser_mock, \
          patch.object(wudd, 'load_json_file', return_value={'10': {'releases': {}}}) as load_json_mock, \
          patch.object(wudd, 'AppConfig', return_value=fake_config) as app_config_mock, \
          patch.dict(sys.modules, {'wuddlib.runner': fake_runner}), \
          patch('os.path.abspath', return_value=str(Path(tmp_dir) / 'wudd.py')), \
          patch('os.path.dirname', return_value=tmp_dir), \
          patch('logging.basicConfig') as logging_basic_config:
        build_parser_mock.return_value.parse_args.return_value = types.SimpleNamespace(
          browser='firefox',
          clean=True,
          download=True,
          foreground=True,
          latest=True,
          logging='debug',
          skipsha1=True,
          workers=4,
          use_snapshot_cache=False,
        )

        wudd.main()

      load_json_mock.assert_called_once_with(str(osinfo_path))
      app_config_mock.assert_called_once()
      fake_runner.run.assert_called_once_with({'10': {'releases': {}}}, fake_config)
      logging_basic_config.assert_any_call(
        format="{asctime} - {levelname} - {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=10,
      )

  def test_main_exits_cleanly_on_keyboard_interrupt(self):
    import wudd

    fake_runner = types.ModuleType('wuddlib.runner')
    fake_runner.run = Mock(side_effect=KeyboardInterrupt())

    with tempfile.TemporaryDirectory() as tmp_dir:
      osinfo_path = Path(tmp_dir) / 'osinfo.json'
      osinfo_path.write_text('{"10": {"releases": {}}}', encoding='utf-8')

      with patch.object(wudd, 'build_parser') as build_parser_mock, \
          patch.object(wudd, 'load_json_file', return_value={'10': {'releases': {}}}), \
          patch.object(wudd, 'AppConfig') as app_config_mock, \
          patch.dict(sys.modules, {'wuddlib.runner': fake_runner}), \
          patch('os.path.abspath', return_value=str(Path(tmp_dir) / 'wudd.py')), \
          patch('os.path.dirname', return_value=tmp_dir), \
          patch('builtins.print') as print_mock:
        build_parser_mock.return_value.parse_args.return_value = types.SimpleNamespace(
          browser='chrome',
          clean=False,
          download=False,
          foreground=False,
          latest=False,
          logging='info',
          skipsha1=False,
          workers=4,
          use_snapshot_cache=True,
        )

        with self.assertRaises(SystemExit) as exit_ctx:
          wudd.main()

    self.assertEqual(exit_ctx.exception.code, 130)
    print_mock.assert_called_once_with('Interrupted, exiting.', file=sys.stderr)
