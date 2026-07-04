from contextlib import contextmanager
import re
import types
import unittest
from unittest.mock import patch

try:
  from selenium.common.exceptions import NoSuchElementException
  from selenium.webdriver.common.by import By
  from wuddlib.catalog import CatalogSearch
  from wuddlib.catalog import CatalogSearchBatch
  from wuddlib.catalog import CatalogSearchResult
  from wuddlib.catalog import _clear_search_index_cache
except Exception as import_error:  # pragma: no cover - skipped when selenium is not installed
  NoSuchElementException = Exception
  By = None
  CatalogSearch = None
  CatalogSearchBatch = None
  CatalogSearchResult = None
  _clear_search_index_cache = lambda: None
  _IMPORT_ERROR = import_error
else:
  _IMPORT_ERROR = None


def build_row(row_id, title, button_id=None):
  button_id = button_id or re.sub(r'_R\d+$', '', row_id)
  return (
    f'<tr id="{row_id}">'
    f'<td id="{button_id}_C1_R0">'
    f'<a id="{button_id}_link" href="javascript:void(0);" onclick=\'goToDetails("{button_id}");\'>'
    f'{title}'
    '</a>'
    '</td>'
    f'<td><input id="{button_id}" class="flatBlueButtonDownload focus-only" type="button" value="Download" /></td>'
    '</tr>'
  )


def build_page(rows, page_number, total_pages):
  row_count = len(rows)
  return (
    '<html><body>'
    f'<span>{1 if row_count else 0} - {row_count} of {row_count} (page {page_number} of {total_pages})</span>'
    '<table id="ctl00_catalogBody_updateMatches">'
    f'{"".join(rows)}'
    '</table>'
    '</body></html>'
  )


class FakeResponse:
  def __init__(self, text):
    self.text = text
    self.encoding = 'utf-8'
    self.apparent_encoding = 'utf-8'

  def raise_for_status(self):
    return None


class FakeSession:
  def __init__(self, responses):
    self.responses = responses
    self.headers = {}
    self.calls = []

  def get(self, url, params=None, timeout=None):
    params = params or {}
    self.calls.append((url, params, timeout))
    query = params.get('q', '')
    page = params.get('p', 0)
    key = (query, page)
    if key not in self.responses:
      raise AssertionError(f'No fake response registered for {key}')
    return self.responses[key]

  def close(self):
    return None


class FakeElement:
  def __init__(self, click_callback=None, element_id='fake-id', click_error=None):
    self._click_callback = click_callback
    self._element_id = element_id
    self._click_error = click_error

  def click(self):
    if self._click_error is not None:
      raise self._click_error
    if self._click_callback is not None:
      self._click_callback()

  def get_attribute(self, name):
    if name == 'id':
      return self._element_id
    return None


class FakeDriver:
  def __init__(self, window_handles=None, page_source_text=''):
    self.opened_urls = []
    self.script_calls = []
    self.find_calls = []
    self.button = None
    self._window_handles = list(window_handles or ['main'])
    self._page_source_text = page_source_text
    self.current_window = self._window_handles[0]
    self.closed_handles = []

  def get(self, url):
    self.opened_urls.append(url)

  def find_element(self, by, value):
    self.find_calls.append((by, value))
    if by == By.ID and value == getattr(self.button, '_element_id', None):
      return self.button
    raise NoSuchElementException()

  def execute_script(self, script, element):
    self.script_calls.append((script, element.get_attribute('id')))

  @property
  def window_handles(self):
    return list(self._window_handles)

  @property
  def switch_to(self):
    class _Switcher:
      def __init__(self, outer):
        self.outer = outer

      def window(self, handle):
        self.outer.current_window = handle
        return None

    return _Switcher(self)

  @property
  def page_source(self):
    return self._page_source_text

  def close(self):
    self.closed_handles.append(self.current_window)
    if self.current_window in self._window_handles:
      self._window_handles.remove(self.current_window)

  def quit(self):
    return None


@unittest.skipUnless(_IMPORT_ERROR is None, 'Install Selenium to run the catalog unit tests')
class CatalogSearchTests(unittest.TestCase):
  def setUp(self):
    _clear_search_index_cache()

  def test_search_parses_broad_http_rows_until_result_is_found(self):
    broad_query = 'Cumulative Update for Windows 11 Version 24H2 for x64-based Systems'
    row_1 = build_row(
      '11111111-1111-1111-1111-111111111111_R0',
      '2025-11 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5070000)',
    )
    row_2 = build_row(
      '22222222-2222-2222-2222-222222222222_R0',
      '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5072033)',
    )
    responses = {
      (broad_query, 0): FakeResponse(build_page([row_1], 1, 2)),
      (broad_query, 1): FakeResponse(build_page([row_2], 2, 2)),
    }
    fake_session = FakeSession(responses)

    with patch('wuddlib.catalog.requests.Session', return_value=fake_session), \
        patch.object(CatalogSearch, '_load_snapshot_result', lambda self: None), \
        patch.object(CatalogSearch, '_dlbutton', lambda self: None), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-12', browser='chrome', foreground=False, use_snapshot_cache=False)

    self.assertIsNotNone(search.searchresult)
    self.assertEqual(search.searchresult.get_attribute('id'), '22222222-2222-2222-2222-222222222222_R0')
    self.assertEqual(search.searchresult.get_attribute('download_button_id'), '22222222-2222-2222-2222-222222222222')
    self.assertIn('p=1', search.searchresult.get_attribute('page_url'))
    self.assertEqual(len(fake_session.calls), 2)
    self.assertEqual(fake_session.calls[0][1].get('q'), broad_query)
    self.assertNotIn('p', fake_session.calls[0][1])
    self.assertEqual(fake_session.calls[1][1].get('p'), 1)

  def test_search_reuses_broad_index_across_multiple_months(self):
    broad_query = 'Cumulative Update for Windows 11 Version 24H2 for x64-based Systems'
    row_1 = build_row(
      '11111111-1111-1111-1111-111111111111_R0',
      '2025-11 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5070000)',
    )
    row_2 = build_row(
      '22222222-2222-2222-2222-222222222222_R0',
      '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5072033)',
    )
    responses = {
      (broad_query, 0): FakeResponse(build_page([row_1], 1, 2)),
      (broad_query, 1): FakeResponse(build_page([row_2], 2, 2)),
    }
    fake_session = FakeSession(responses)

    with patch('wuddlib.catalog.requests.Session', return_value=fake_session), \
        patch.object(CatalogSearch, '_load_snapshot_result', lambda self: None), \
        patch.object(CatalogSearch, '_dlbutton', lambda self: None), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search_nov = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-11', browser='chrome', foreground=False, use_snapshot_cache=False)
      search_dec = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-12', browser='chrome', foreground=False, use_snapshot_cache=False)

    self.assertEqual(search_nov.searchresult.get_attribute('id'), '11111111-1111-1111-1111-111111111111_R0')
    self.assertEqual(search_dec.searchresult.get_attribute('id'), '22222222-2222-2222-2222-222222222222_R0')
    self.assertEqual(len(fake_session.calls), 2)

  def test_download_button_uses_javascript_click_when_native_click_fails(self):
    update_id = 'ee3d478c-76c1-47ed-9749-c2e814f16001'
    button_id = update_id
    fake_driver = FakeDriver()
    fake_driver.button = FakeElement(
      element_id=button_id,
      click_error=Exception('element not interactable'),
    )
    searchresult = CatalogSearchResult(
      row_id=f'{update_id}_R0',
      download_button_id=button_id,
      page_url='https://www.catalog.update.microsoft.com/Search.aspx?q=test&p=2',
      title='2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5072033)',
      row_text='2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5072033)',
    )

    def _set_searchresult(self):
      self.searchresult = searchresult

    def _set_driver(self):
      self.driver = fake_driver
      return fake_driver

    with patch.object(CatalogSearch, '_searchresult', _set_searchresult), \
        patch.object(CatalogSearch, '_driver', _set_driver), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-12', browser='chrome', foreground=False, use_snapshot_cache=False)

    self.assertIsNotNone(search.searchresult)
    self.assertEqual(fake_driver.opened_urls, [searchresult.get_attribute('page_url')])
    self.assertTrue(any(call[0] == "arguments[0].click();" for call in fake_driver.script_calls))

  def test_search_uses_kb_hint_fallback_when_exact_title_match_fails(self):
    broad_query = 'Cumulative Update for Windows 11 Version 24H2 for x64-based Systems'
    row_without_kb = build_row(
      '33333333-3333-3333-3333-333333333333_R0',
      '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5071111)',
    )
    row_with_kb = build_row(
      '44444444-4444-4444-4444-444444444444_R0',
      '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5072033)',
    )
    responses = {
      (broad_query, 0): FakeResponse(build_page([row_without_kb, row_with_kb], 1, 1)),
    }
    fake_session = FakeSession(responses)

    with patch('wuddlib.catalog.requests.Session', return_value=fake_session), \
        patch.object(CatalogSearch, '_load_snapshot_result', lambda self: None), \
        patch.object(CatalogSearch, '_load_kb_hint', lambda self: 'KB5072033'), \
        patch.object(CatalogSearch, '_dlbutton', lambda self: None), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-12', browser='chrome', foreground=False, use_snapshot_cache=False)

    self.assertIsNotNone(search.searchresult)
    self.assertEqual(search.searchresult.get_attribute('id'), '44444444-4444-4444-4444-444444444444_R0')
    self.assertEqual(search.searchresult.get_attribute('download_button_id'), '44444444-4444-4444-4444-444444444444')
    self.assertEqual(len(fake_session.calls), 1)
    self.assertEqual(fake_session.calls[0][1].get('q'), broad_query)

  def test_search_uses_snapshot_fallback_when_live_search_returns_no_match(self):
    exact_query = '2024-01 Cumulative Update for Windows 10 Version 21H2 for x64'
    broad_query = 'Cumulative Update for Windows 10 Version 21H2 for x64-based Systems'
    snapshot = {
      'osver': '10',
      'release': '21H2',
      'arch': 'x64',
      'date': '2024-01',
      'updateID': 'a2c3d773-7083-4aa8-b424-5893d2e75431',
      'title': '2024-01 Cumulative Update for Windows 10 Version 21H2 for x64-based Systems (KB5034122)',
      'kb': 'KB5034122',
      'files': ['https://example.invalid/windows10.msu'],
      'sha1': ['de14dfac8817c1d0765b899125c63dc7b581958b'],
    }
    responses = {
      (broad_query, 0): FakeResponse(build_page([], 1, 1)),
      (exact_query, 0): FakeResponse(build_page([], 1, 1)),
    }
    fake_session = FakeSession(responses)

    with patch('wuddlib.catalog.requests.Session', return_value=fake_session), \
        patch.object(CatalogSearch, '_load_snapshot_result', side_effect=[None, snapshot]), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch('10', '21H2', 'x64', 'cu', '2024-01', browser='chrome', foreground=False)

    self.assertIsNotNone(search.searchresult)
    self.assertEqual(search.searchresult.get_attribute('id'), snapshot['updateID'])
    self.assertEqual(search.dl_info_dict['kb'], 'KB5034122')
    self.assertEqual(len(fake_session.calls), 3)
    self.assertEqual(fake_session.calls[0][1].get('q'), broad_query)
    self.assertEqual(fake_session.calls[1][1].get('q'), exact_query)
    self.assertEqual(fake_session.calls[2][1].get('q'), broad_query)

  def test_search_can_disable_snapshot_cache_for_live_lookups(self):
    broad_query = 'Cumulative Update for Windows 11 Version 24H2 for x64-based Systems'
    row = build_row(
      '44444444-4444-4444-4444-444444444444_R0',
      '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5072033)',
    )
    responses = {
      (broad_query, 0): FakeResponse(build_page([row], 1, 1)),
    }
    fake_session = FakeSession(responses)

    with patch('wuddlib.catalog.requests.Session', return_value=fake_session), \
        patch.object(CatalogSearch, '_load_snapshot_result', side_effect=AssertionError('snapshot cache should be disabled')), \
        patch.object(CatalogSearch, '_dlbutton', lambda self: None), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch(
        '11',
        '24H2',
        'x64',
        'cu',
        '2025-12',
        browser='chrome',
        foreground=False,
        use_snapshot_cache=False,
      )

    self.assertIsNotNone(search.searchresult)
    self.assertEqual(search.searchresult.get_attribute('id'), '44444444-4444-4444-4444-444444444444_R0')
    self.assertEqual(len(fake_session.calls), 1)

  def test_download_info_closes_popup_windows_for_browser_reuse(self):
    page_source = (
      "downloadInformation[0].updateID = 'abc123';\n"
      "downloadInformation[0].enTitle = '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5072033)';\n"
      "downloadInformation[0].files[0].url = 'https://example.invalid/update_x64_abc123.msu';\n"
    )
    fake_driver = FakeDriver(window_handles=['main', 'popup'], page_source_text=page_source)
    search = object.__new__(CatalogSearch)
    search.driver = fake_driver
    search.dl_info_dict = {}
    search.osver = '11'
    search.release = '24H2'
    search.arch = 'x64'
    search.date = '2025-12'

    CatalogSearch._dlinfo(search)

    self.assertEqual(search.dl_info_dict['updateID'], 'abc123')
    self.assertEqual(search.dl_info_dict['kb'], 'KB5072033')
    self.assertEqual(fake_driver.closed_handles, ['popup'])
    self.assertEqual(fake_driver.current_window, 'main')

  def test_catalog_batch_reuses_one_browser_session_across_resolves(self):
    if CatalogSearch is None or CatalogSearchBatch is None:
      self.skipTest('CatalogSearch is unavailable')

    class FakeBrowserSession:
      def __init__(self):
        self._driver = None
        self.create_count = 0
        self.use_count = 0
        self.close_count = 0

      @property
      def driver(self):
        if self._driver is None:
          self._driver = object()
          self.create_count += 1
        return self._driver

      @contextmanager
      def use(self):
        self.use_count += 1
        yield self.driver

      def close(self):
        self.close_count += 1

    class FakeSearch:
      def __init__(self, update_date):
        self.date = update_date
        self.driver = None
        self.owns_driver = True
        self.searchresult = None
        self.dl_info_dict = {}
        self.session = types.SimpleNamespace(close=lambda: None)

      def _load_snapshot_result(self):
        return None

      def _find_indexed_searchresult(self, search_index):
        self.searchresult = types.SimpleNamespace(
          get_attribute=lambda name: {
            'id': f'{self.date}-row',
            'download_button_id': f'{self.date}-button',
            'page_url': f'https://example.invalid/{self.date}',
          }.get(name)
        )
        return self.searchresult

      def _searchresult(self):
        raise AssertionError('search discovery should not be needed for indexed batch results')

      def _dlbutton(self):
        self.dl_info_dict['driver_id'] = id(self.driver)

      def _dlinfo(self):
        self.dl_info_dict['ok'] = True

    def fake_build_search_context(
      osver,
      release,
      arch,
      update_type,
      update_date,
      browser,
      foreground,
      use_snapshot_cache=True,
      driver=None,
    ):
      return FakeSearch(update_date)

    batch = object.__new__(CatalogSearchBatch)
    batch.osver = '11'
    batch.release = '24H2'
    batch.arch = 'x64'
    batch.update_type = 'cu'
    batch.browser = 'chrome'
    batch.foreground = False
    batch.use_snapshot_cache = False
    batch.prime_update_date = '2025-12'
    batch.search_index = {'rows': [1], 'by_date': {'2025-12': [1], '2026-01': [1]}}
    batch.browser_session = FakeBrowserSession()

    with patch('wuddlib.catalog._build_search_context', side_effect=fake_build_search_context):
      first = batch.resolve('2025-12')
      second = batch.resolve('2026-01')

    self.assertEqual(batch.browser_session.create_count, 1)
    self.assertEqual(batch.browser_session.use_count, 2)
    self.assertEqual(first.dl_info_dict['driver_id'], second.dl_info_dict['driver_id'])
    self.assertIs(first.driver, second.driver)
    self.assertTrue(first.dl_info_dict['ok'])
    self.assertTrue(second.dl_info_dict['ok'])

    batch.close()
    self.assertEqual(batch.browser_session.close_count, 1)
