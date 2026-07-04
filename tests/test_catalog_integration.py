import os
import unittest

try:
  from selenium.common.exceptions import WebDriverException
  from wuddlib.catalog import CatalogSearch
except Exception as import_error:  # pragma: no cover - exercised only when optional deps are missing
  WebDriverException = Exception
  CatalogSearch = None
  _IMPORT_ERROR = import_error
else:
  _IMPORT_ERROR = None


@unittest.skipUnless(os.getenv('WUDD_INTEGRATION') == '1', 'Set WUDD_INTEGRATION=1 to run live Selenium integration tests')
class CatalogIntegrationTests(unittest.TestCase):
  def test_live_catalog_search_smoke(self):
    if _IMPORT_ERROR is not None:
      self.skipTest(f'Optional Selenium integration dependencies are unavailable: {_IMPORT_ERROR}')

    browser = os.getenv('WUDD_INTEGRATION_BROWSER', 'chrome')

    try:
      search = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-12', browser=browser, foreground=False)
    except WebDriverException as error:
      self.skipTest(f'WebDriver is not available in this environment: {error}')

    self.assertEqual(search.searchterm, '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64')
    self.assertIsNotNone(search.searchresult)
    self.assertEqual(search.dl_info_dict['osver'], '11')
    self.assertEqual(search.dl_info_dict['release'], '24H2')
    self.assertEqual(search.dl_info_dict['arch'], 'x64')
    self.assertEqual(search.dl_info_dict['date'], '2025-12')
    self.assertEqual(search.dl_info_dict['kb'], 'KB5072033')
    self.assertGreaterEqual(len(search.dl_info_dict.get('files', [])), 1)
    self.assertGreaterEqual(len(search.dl_info_dict.get('sha1', [])), 1)

