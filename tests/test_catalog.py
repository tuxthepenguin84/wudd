import unittest
from unittest.mock import patch

try:
  from selenium.common.exceptions import NoSuchElementException
  from selenium.webdriver.common.by import By
  from wuddlib.catalog import CatalogSearch
except Exception as import_error:  # pragma: no cover - skipped when selenium is not installed
  NoSuchElementException = Exception
  By = None
  CatalogSearch = None
  _IMPORT_ERROR = import_error
else:
  _IMPORT_ERROR = None


class FakeElement:
  def __init__(
    self,
    click_callback=None,
    element_id='fake-id',
    click_error=None,
    child_elements=None,
    text='',
    element_lookup=None,
  ):
    self._click_callback = click_callback
    self._element_id = element_id
    self._click_error = click_error
    self._child_elements = child_elements or []
    self.text = text
    self._element_lookup = element_lookup or {}

  def click(self):
    if self._click_error is not None:
      raise self._click_error
    if self._click_callback is not None:
      self._click_callback()

  def get_attribute(self, name):
    if name == 'id':
      return self._element_id
    return None

  def find_elements(self, by, value):
    return list(self._child_elements)

  def find_element(self, by, value):
    key = (by, value)
    if key in self._element_lookup:
      return self._element_lookup[key]
    raise NoSuchElementException()


class FakeDriver:
  def __init__(self, result_page=3):
    self.result_page = result_page
    self.current_page = 1
    self.opened_urls = []
    self.current_url = ''
    self.script_calls = []
    self.fallback_rows = []

  def get(self, url):
    self.opened_urls.append(url)
    self.current_url = url

  def find_element(self, by, value):
    if by == By.XPATH and "2025-12 Cumulative Update for Windows 11 Version 24H2 for x64" in value:
      if self.current_page == self.result_page:
        download_button = FakeElement(element_id='ctl00_catalogBody_downloadButton_123')
        return FakeElement(element_id='ctl00_catalogBody_updateMatches_123', child_elements=[download_button])
      raise NoSuchElementException()

    if by == By.ID and value in {'ctl00_catalogBody_nextPageLinkText', 'ctl00_catalogBody_nextPageLinkButton'}:
      if self.current_page < self.result_page:
        return FakeElement(click_callback=self._advance_page, element_id=value)
      raise NoSuchElementException()

    raise NoSuchElementException()

  def find_elements(self, by, value):
    if by == By.XPATH and value == "//table[@id='ctl00_catalogBody_updateMatches']//tr[td]" and 'x64-based' in self.current_url:
      return list(self.fallback_rows)
    return []

  def execute_script(self, script, element):
    self.script_calls.append((script, element.get_attribute('id')))
    return None

  def _advance_page(self):
    self.current_page += 1

  @property
  def page_source(self):
    return ''

  @property
  def window_handles(self):
    return ['main']

  @property
  def switch_to(self):
    class _Switcher:
      def window(self, handle):
        return None

    return _Switcher()

  def quit(self):
    return None


@unittest.skipUnless(_IMPORT_ERROR is None, 'Install Selenium to run the catalog pagination unit test')
class CatalogSearchTests(unittest.TestCase):
  def test_search_advances_pages_until_result_is_found(self):
    fake_driver = FakeDriver(result_page=3)

    with patch.object(CatalogSearch, '_driver', lambda self: setattr(self, 'driver', fake_driver)), \
        patch.object(CatalogSearch, '_dlbutton', lambda self: None), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-12', browser='chrome', foreground=False)

    self.assertIsNotNone(search.searchresult)
    self.assertEqual(fake_driver.current_page, 3)
    self.assertEqual(len(fake_driver.opened_urls), 1)
    self.assertEqual(search.searchterm, '2025-12 Cumulative Update for Windows 11 Version 24H2 for x64')

  def test_download_button_uses_javascript_click_when_native_click_fails(self):
    fake_driver = FakeDriver(result_page=1)
    update_id = 'ee3d478c-76c1-47ed-9749-c2e814f16001'

    def find_element(by, value):
      if by == By.XPATH and "2025-12 Cumulative Update for Windows 11 Version 24H2 for x64" in value:
        return FakeElement(element_id=f'{update_id}_C1_R0')
      if by == By.XPATH and f"//*[@id='{update_id}']" in value:
        return FakeElement(
          element_id=update_id,
          click_error=Exception('element not interactable'),
        )
      raise NoSuchElementException()

    fake_driver.find_element = find_element

    with patch.object(CatalogSearch, '_driver', lambda self: setattr(self, 'driver', fake_driver)), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-12', browser='chrome', foreground=False)

    self.assertIsNotNone(search.searchresult)
    self.assertTrue(any(call[0].endswith("arguments[0].click();") for call in fake_driver.script_calls))

  def test_search_uses_kb_hint_fallback_when_exact_title_match_fails(self):
    fake_driver = FakeDriver(result_page=1)
    update_id = 'ee3d478c-76c1-47ed-9749-c2e814f16001'
    download_button = FakeElement(element_id=update_id)
    row = FakeElement(
      element_id=f'{update_id}_R0',
      text='2025-12 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5072033)',
      element_lookup={
        (By.XPATH, ".//input[@type='button']"): download_button,
      },
    )
    fake_driver.fallback_rows = [row]

    def find_element(by, value):
      if by == By.XPATH and "2025-12 Cumulative Update for Windows 11 Version 24H2 for x64" in value:
        raise NoSuchElementException()
      if by == By.XPATH and f"//*[@id='{update_id}']" in value:
        return download_button
      raise NoSuchElementException()

    fake_driver.find_element = find_element

    with patch.object(CatalogSearch, '_driver', lambda self: setattr(self, 'driver', fake_driver)), \
        patch.object(CatalogSearch, '_load_kb_hint', lambda self: 'KB5072033'), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch('11', '24H2', 'x64', 'cu', '2025-12', browser='chrome', foreground=False)

    self.assertIsNotNone(search.searchresult)
    self.assertEqual(search.searchresult.get_attribute('id'), update_id)
    self.assertEqual(len(fake_driver.opened_urls), 2)
    self.assertIn('x64-based%20Systems', fake_driver.opened_urls[1])

  def test_search_uses_snapshot_fallback_when_live_search_returns_no_match(self):
    fake_driver = FakeDriver(result_page=1)
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

    def find_element(by, value):
      raise NoSuchElementException()

    fake_driver.find_element = find_element

    with patch.object(CatalogSearch, '_driver', lambda self: setattr(self, 'driver', fake_driver)), \
        patch.object(CatalogSearch, '_load_kb_hint', lambda self: 'KB5034122'), \
        patch.object(CatalogSearch, '_load_snapshot_result', lambda self: snapshot), \
        patch.object(CatalogSearch, '_dlinfo', lambda self: None):
      search = CatalogSearch('10', '21H2', 'x64', 'cu', '2024-01', browser='chrome', foreground=False)

    self.assertIsNotNone(search.searchresult)
    self.assertEqual(search.searchresult.get_attribute('id'), snapshot['updateID'])
    self.assertEqual(search.dl_info_dict['kb'], 'KB5034122')
    self.assertEqual(len(fake_driver.opened_urls), 2)
