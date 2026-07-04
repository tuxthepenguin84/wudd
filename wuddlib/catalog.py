import html
import json
import logging
import os
import re
import sys
import time
import urllib.parse
from functools import lru_cache
from contextlib import contextmanager
import threading

import requests
from selenium import webdriver
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_PATHS = [
  os.path.join(REPO_ROOT, 'stored', 'wudd.json'),
  os.path.join(REPO_ROOT, 'outputs', 'wudd.json'),
]
CATALOG_SEARCH_URL = 'https://www.catalog.update.microsoft.com/Search.aspx'
REQUEST_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  'Accept-Language': 'en-US,en;q=0.9',
}
SEARCH_INDEX_CACHE = {}

ROW_RE = re.compile(r'<tr id="(?P<row_id>[^"]+)"[^>]*>(?P<body>.*?)</tr>', re.S | re.I)
TITLE_RE = re.compile(r"<a[^>]+id=['\"](?P<link_id>[^'\"]+)_link['\"][^>]*>(?P<title>.*?)</a>", re.S | re.I)
PAGE_INFO_RE = re.compile(
  r'(?P<start>\d+)\s*-\s*(?P<end>\d+)\s*of\s*(?P<total>\d+)\s*\(page\s*(?P<page>\d+)\s*of\s*(?P<pages>\d+)\)',
  re.I,
)


class SnapshotSearchResult:
  def __init__(self, update_id):
    self._update_id = update_id

  def get_attribute(self, name):
    if name == 'id':
      return self._update_id
    return None


class CatalogSearchResult:
  def __init__(self, row_id, download_button_id, page_url, title='', row_text=''):
    self._attributes = {
      'id': row_id,
      'download_button_id': download_button_id,
      'page_url': page_url,
      'title': title,
      'row_text': row_text,
    }

  def get_attribute(self, name):
    return self._attributes.get(name)


@lru_cache(maxsize=2)
def _load_snapshot_file(snapshot_path):
  if not os.path.isfile(snapshot_path):
    return None
  try:
    with open(snapshot_path, 'r', encoding='utf-8') as snapshot_file:
      return json.load(snapshot_file)
  except Exception as error:
    logging.debug(f"Could not load snapshot from {snapshot_path}: {error}")
    return None


def _title_matches_update_type(title, update_type):
  lowered_title = title.lower()
  if update_type == 'dcu':
    return 'dynamic cumulative update' in lowered_title
  if update_type == 'cup':
    return 'cumulative update' in lowered_title and 'preview' in lowered_title
  if update_type == 'dnet':
    return '.net framework' in lowered_title and 'preview' not in lowered_title
  if update_type == 'dnetp':
    return '.net framework' in lowered_title and 'preview' in lowered_title
  return 'cumulative update' in lowered_title and 'dynamic cumulative update' not in lowered_title


@lru_cache(maxsize=1024)
def _lookup_snapshot_result(osver, release, arch, date, update_type):
  for snapshot_path in SNAPSHOT_PATHS:
    snapshot_data = _load_snapshot_file(snapshot_path)
    if not snapshot_data:
      continue

    try:
      date_records = snapshot_data[osver][release][arch][date]
    except KeyError:
      continue

    for update_id, record in date_records.items():
      title = record.get('title', '')
      if _title_matches_update_type(title, update_type):
        kb = record.get('kb')
        files = record.get('files', [])
        sha1 = record.get('sha1', [])
        if kb and files and sha1:
          return {
            'osver': osver,
            'release': release,
            'arch': arch,
            'date': date,
            'updateID': update_id,
            'title': title,
            'kb': kb,
            'files': files,
            'sha1': sha1,
          }

    if date_records:
      update_id, record = next(iter(date_records.items()))
      kb = record.get('kb')
      files = record.get('files', [])
      sha1 = record.get('sha1', [])
      if kb and files and sha1:
        return {
          'osver': osver,
          'release': release,
          'arch': arch,
          'date': date,
          'updateID': update_id,
          'title': record.get('title', ''),
          'kb': kb,
          'files': files,
          'sha1': sha1,
        }

  return None


@lru_cache(maxsize=1024)
def _lookup_kb_hint(osver, release, arch, date, update_type):
  snapshot_result = _lookup_snapshot_result(osver, release, arch, date, update_type)
  if snapshot_result:
    return snapshot_result.get('kb')
  return None


def _normalize_text(text):
  return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', text)).split())


def _clear_search_index_cache():
  SEARCH_INDEX_CACHE.clear()


def _row_date_from_title(title):
  match = re.match(r'(?P<date>\d{4}-\d{2})\b', title)
  if match:
    return match.group('date')
  return None


def _build_search_context(osver, release, arch, update_type, update_date, browser, foreground, use_snapshot_cache=True):
  return _build_search_context_with_driver(
    osver,
    release,
    arch,
    update_type,
    update_date,
    browser,
    foreground,
    use_snapshot_cache=use_snapshot_cache,
  )


def _create_webdriver(browser, foreground):
  if browser == 'firefox':
    browser_options = FirefoxOptions()
    if not foreground:
      browser_options.add_argument('--headless')
    return webdriver.Firefox(options=browser_options)

  browser_options = ChromeOptions()
  if not foreground:
    browser_options.add_argument('--headless')
  return webdriver.Chrome(options=browser_options)


def _build_search_context_with_driver(
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
  search = object.__new__(CatalogSearch)
  search.osver = osver
  search.release = release
  search.arch = arch
  search.type = update_type
  search.date = update_date
  search.browser = browser
  search.foreground = foreground
  search.use_snapshot_cache = use_snapshot_cache
  search.driver = None
  search.owns_driver = driver is None
  search.driver = driver
  search.searchresult = None
  search.dl_info_dict = {}
  search._kb_hint = None
  search.session = requests.Session()
  search.session.headers.update(REQUEST_HEADERS)
  search._searchterm()
  search.fallback_searchterm = search._fallback_searchterm()
  search.searchurl = f"{CATALOG_SEARCH_URL}?q={urllib.parse.quote(search.searchterm)}"
  return search


class _BrowserSession:
  def __init__(self, browser, foreground):
    self.browser = browser
    self.foreground = foreground
    self._driver = None
    self._lock = threading.Lock()

  @property
  def driver(self):
    if self._driver is None:
      self._driver = _create_webdriver(self.browser, self.foreground)
    return self._driver

  @contextmanager
  def use(self):
    with self._lock:
      yield self.driver

  def close(self):
    if self._driver is None:
      return
    try:
      self._driver.quit()
    finally:
      self._driver = None


def _parse_total_pages(page_html):
  page_info_match = PAGE_INFO_RE.search(page_html)
  if not page_info_match:
    return 1
  try:
    return int(page_info_match.group('pages'))
  except (TypeError, ValueError):
    return 1


def _parse_search_rows(page_html, page_url):
  rows = []
  for row_match in ROW_RE.finditer(page_html):
    row_id = row_match.group('row_id')
    row_body = row_match.group('body')
    title_match = TITLE_RE.search(row_body)
    if not title_match:
      continue

    title = _normalize_text(title_match.group('title'))
    row_text = _normalize_text(row_body)
    download_button_id = title_match.group('link_id')
    if not download_button_id:
      download_button_id = re.sub(r'_R\d+$', '', row_id)

    rows.append(
      CatalogSearchResult(
        row_id=row_id,
        download_button_id=download_button_id,
        page_url=page_url,
        title=title,
        row_text=row_text,
      )
    )
  return rows


class CatalogSearch:
  def __init__(
    self,
    osver,
    release,
    arch,
    update_type,
    update_date,
    browser,
    foreground,
    use_snapshot_cache=True,
    driver=None,
    owns_driver=True,
  ):
    self.osver = osver
    self.release = release
    self.arch = arch
    self.type = update_type
    self.date = update_date
    self.browser = browser
    self.foreground = foreground
    self.use_snapshot_cache = use_snapshot_cache
    self.driver = driver
    self.owns_driver = owns_driver if driver is None else False
    self.searchresult = None
    self.dl_info_dict = {}
    self._kb_hint = None
    self.session = requests.Session()
    self.session.headers.update(REQUEST_HEADERS)

    try:
      self._searchterm()
      self.fallback_searchterm = self._fallback_searchterm()
      self.searchurl = f"{CATALOG_SEARCH_URL}?q={urllib.parse.quote(self.searchterm)}"

      if self.use_snapshot_cache:
        snapshot_result = self._load_snapshot_result()
        if snapshot_result:
          self.dl_info_dict = snapshot_result
          self.searchresult = SnapshotSearchResult(snapshot_result['updateID'])
          logging.debug(f"Loaded snapshot cache for: {self.searchterm}")
          return

      self._searchresult()
      if self.searchresult and not self.dl_info_dict:
        self._dlbutton()
        self._dlinfo()
    finally:
      self.session.close()
      if self.owns_driver and self.driver is not None:
        self.driver.quit()

  def _searchterm(self):
    update_type = {
      'cu': 'Cumulative Update',
      'dcu': 'Dynamic Cumulative Update',
      'cup': 'Cumulative Update Preview',
      'dnet': 'Cumulative Update for .NET Framework 3.5, 4.8 and 4.8.1',
      'dnetp': 'Cumulative Update Preview for .NET Framework 3.5, 4.8 and 4.8.1',
      'custom': None,
    }
    if self.type == 'custom':
      logging.error('Custom search terms not available yet')
      sys.exit(0)
    if self.type in update_type:
      update_string = update_type[self.type]
      self.searchterm = f"{self.date} {update_string} for Windows {self.osver} Version {self.release} for {self.arch}"
      return
    logging.error(f"Invalid update type: {self.type}")
    sys.exit(1)

  def _driver(self):
    if self.driver is not None:
      return self.driver

    self.driver = _create_webdriver(self.browser, self.foreground)
    self.owns_driver = True
    return self.driver

  def _searchresult(self):
    search_index = self._load_search_index()
    if search_index:
      searchresult = self._find_indexed_searchresult(search_index)
      if searchresult:
        self.searchresult = searchresult
        logging.debug(f"Search Result Element ID: {self.searchresult.get_attribute('id')}")
        logging.debug(f"broad search index found for {self.date}")
        return
      logging.debug(f"No broad search index result for {self.date}; falling back to exact title search")

    if self._search_pages(self.searchterm, self._find_exact_searchresult, 'exact title search'):
      return

    if self.fallback_searchterm and self.fallback_searchterm != self.searchterm:
      if self._search_pages(self.fallback_searchterm, self._find_exact_or_kb_searchresult, 'fallback search'):
        return

    snapshot_result = self._load_snapshot_result()
    if snapshot_result:
      self.dl_info_dict = snapshot_result
      self.searchresult = SnapshotSearchResult(snapshot_result['updateID'])
      logging.debug(f"Loaded snapshot fallback for: {self.searchterm}")
      return

    logging.warning(f"No results for: {self.searchterm}")
    self.searchresult = None

  def _search_pages(self, search_query, finder, search_label):
    page_index = 0
    total_pages = None
    while True:
      page_html, page_url = self._fetch_search_page(search_query, page_index)
      if page_html is None:
        return False

      if total_pages is None:
        total_pages = _parse_total_pages(page_html)
      rows = _parse_search_rows(page_html, page_url)
      searchresult = finder(rows)
      if searchresult:
        self.searchresult = searchresult
        logging.debug(f"Search Result Element ID: {self.searchresult.get_attribute('id')}")
        logging.debug(f"{search_label} found on page {page_index + 1}")
        return True

      logging.debug(f"No {search_label} result on page {page_index + 1} for: {self.searchterm}")
      page_index += 1
      if total_pages is not None and page_index >= total_pages:
        return False

  def _search_index_key(self):
    return (self.osver, self.release, self.arch, self.type)

  def _load_search_index(self):
    cache_key = self._search_index_key()
    if cache_key in SEARCH_INDEX_CACHE:
      return SEARCH_INDEX_CACHE[cache_key]

    search_query = self.fallback_searchterm or self.searchterm
    search_index = {
      'query': search_query,
      'rows': [],
      'by_date': {},
    }

    page_index = 0
    total_pages = None
    while True:
      page_html, page_url = self._fetch_search_page(search_query, page_index)
      if page_html is None:
        return None

      if total_pages is None:
        total_pages = _parse_total_pages(page_html)

      rows = _parse_search_rows(page_html, page_url)
      for row in rows:
        search_index['rows'].append(row)
        row_date = _row_date_from_title(row.get_attribute('title') or '')
        if row_date:
          search_index['by_date'].setdefault(row_date, []).append(row)

      page_index += 1
      if total_pages is not None and page_index >= total_pages:
        break

    if search_index['rows']:
      SEARCH_INDEX_CACHE[cache_key] = search_index
      logging.debug(f"Loaded search index for {search_query}")
      return search_index
    return None

  def _fetch_search_page(self, search_query, page_index):
    params = {'q': search_query}
    if page_index > 0:
      params['p'] = page_index

    page_url = f"{CATALOG_SEARCH_URL}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
    try:
      response = self.session.get(CATALOG_SEARCH_URL, params=params, timeout=30)
      response.raise_for_status()
      if not response.encoding:
        response.encoding = response.apparent_encoding or 'utf-8'
      return response.text, page_url
    except requests.RequestException as error:
      logging.debug(f"Could not fetch catalog search page {page_index + 1} for {search_query}: {error}")
      return None, page_url

  def _find_exact_searchresult(self, rows):
    searchterm = self.searchterm.lower()
    for row in rows:
      title = (row.get_attribute('title') or '').lower()
      if searchterm in title:
        return row
    return None

  def _find_exact_or_kb_searchresult(self, rows):
    exact_result = self._find_exact_searchresult(rows)
    if exact_result:
      return exact_result
    return self._find_fallback_searchresult(rows)

  def _find_indexed_searchresult(self, search_index):
    rows = search_index.get('by_date', {}).get(self.date, [])
    if not rows:
      return None
    kb_hint = self._load_kb_hint()
    for row in rows:
      row_text = row.get_attribute('row_text') or ''
      if not self._row_matches_metadata(row_text):
        continue
      if kb_hint and kb_hint.lower() not in row_text.lower():
        continue
      return row
    return None

  def _fallback_searchterm(self):
    arch_term = f"{self.arch}-based Systems" if self.arch in {'x64', 'arm64', 'x86'} else self.arch
    fallback_types = {
      'cu': f"Cumulative Update for Windows {self.osver} Version {self.release} for {arch_term}",
      'dcu': f"Dynamic Cumulative Update for Windows {self.osver} Version {self.release} for {arch_term}",
      'cup': f"Cumulative Update Preview for Windows {self.osver} Version {self.release} for {arch_term}",
      'dnet': f"Cumulative Update for .NET Framework 3.5, 4.8 and 4.8.1 for Windows {self.osver} Version {self.release} for {self.arch}",
      'dnetp': f"Cumulative Update Preview for .NET Framework 3.5, 4.8 and 4.8.1 for Windows {self.osver} Version {self.release} for {self.arch}",
    }
    return fallback_types.get(self.type)

  def _find_fallback_searchresult(self, rows):
    kb_hint = self._load_kb_hint()
    for row in rows:
      row_text = row.get_attribute('row_text') or ''
      if not self._row_matches_metadata(row_text):
        continue
      if kb_hint and kb_hint.lower() not in row_text.lower():
        continue
      return row
    return None

  def _row_matches_metadata(self, row_text):
    lowered_row_text = row_text.lower()
    required_fragments = [
      f"windows {self.osver}".lower(),
      f"version {self.release}".lower(),
    ]
    if self.arch == 'x64':
      required_fragments.append('x64-based systems')
    elif self.arch == 'arm64':
      required_fragments.append('arm64-based systems')
    elif self.arch == 'x86':
      required_fragments.append('x86-based systems')

    update_type_fragments = {
      'cu': ['cumulative update'],
      'dcu': ['dynamic cumulative update'],
      'cup': ['cumulative update', 'preview'],
      'dnet': ['.net framework'],
      'dnetp': ['.net framework', 'preview'],
    }.get(self.type, [])

    for fragment in required_fragments + update_type_fragments:
      if fragment not in lowered_row_text:
        return False
    return True

  def _load_kb_hint(self):
    if not self.use_snapshot_cache:
      return None
    if self._kb_hint is not None:
      return self._kb_hint
    self._kb_hint = _lookup_kb_hint(self.osver, self.release, self.arch, self.date, self.type)
    return self._kb_hint

  def _load_snapshot_result(self):
    if not self.use_snapshot_cache:
      return None
    return _lookup_snapshot_result(self.osver, self.release, self.arch, self.date, self.type)

  def _title_matches_update_type(self, title):
    return _title_matches_update_type(title, self.type)

  def _click_element(self, element, description):
    try:
      self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", element)
    except Exception as error:
      logging.debug(f"Could not scroll {description} into view: {error}")

    try:
      element.click()
      return True
    except (ElementNotInteractableException, WebDriverException) as error:
      logging.debug(f"Native click failed for {description}: {error}")
    except Exception as error:
      logging.debug(f"Unexpected native click failure for {description}: {error}")

    try:
      self.driver.execute_script("arguments[0].click();", element)
      return True
    except Exception as error:
      logging.debug(f"JavaScript click failed for {description}: {error}")
      return False

  def _dlbutton(self):
    try:
      driver = self._driver()
      page_url = self.searchresult.get_attribute('page_url') or self.searchurl
      if page_url:
        driver.get(page_url)

      dl_button = self.searchresult.get_attribute('download_button_id')
      if not dl_button:
        dl_button = re.sub(r"_\w+$", "", self.searchresult.get_attribute('id'))
      logging.debug(f"Download Button Element ID: {dl_button}")
      dl_link = driver.find_element(By.ID, dl_button)
      logging.debug('Clicking download button...')
      if not self._click_element(dl_link, 'download button'):
        raise RuntimeError('Download button click failed')
    except Exception as error:
      logging.error(f"An error occurred getting download button: {error}")
      sys.exit(1)

  def _dlinfo(self):
    try:
      handles = self.driver.window_handles
      self.driver.switch_to.window(handles[-1])
      dl_info_results = []
      while dl_info_results == []:
        dl_info_pattern = r"downloadInformation\[\d+\]\.(updateID|enTitle|files\[\d+\].url)\s=.*'(.*?)';\n"
        dl_info_results = re.findall(dl_info_pattern, self.driver.page_source)
        if dl_info_results == []:
          time.sleep(0.25)
      for key, value in dl_info_results:
        if key.startswith('files') and key.endswith('.url'):
          self.dl_info_dict.setdefault('files', []).append(value)
          sha1_pattern = r"https://.*_(.*?).(cab|msu)"
          sha1_results = re.search(sha1_pattern, value).group(1)
          self.dl_info_dict.setdefault('sha1', []).append(sha1_results)
        elif key == 'enTitle':
          self.dl_info_dict['title'] = value
          kb_pattern = r'KB\d+'
          kb_results = re.search(kb_pattern, self.dl_info_dict['title']).group()
          self.dl_info_dict['kb'] = kb_results
          self.dl_info_dict['osver'] = self.osver
          self.dl_info_dict['release'] = self.release
          self.dl_info_dict['arch'] = self.arch
          self.dl_info_dict['date'] = self.date
        else:
          self.dl_info_dict[key] = value
    except Exception as error:
      logging.error(f"An error occurred getting download info: {error}")
      sys.exit(1)
    finally:
      self._close_download_windows()

  def _close_download_windows(self):
    try:
      handles = list(self.driver.window_handles)
    except Exception as error:
      logging.debug(f"Could not inspect download windows: {error}")
      return

    if len(handles) <= 1:
      return

    main_handle = handles[0]
    for handle in reversed(handles[1:]):
      try:
        self.driver.switch_to.window(handle)
        self.driver.close()
      except Exception as error:
        logging.debug(f"Could not close download window {handle}: {error}")

    try:
      self.driver.switch_to.window(main_handle)
    except Exception as error:
      logging.debug(f"Could not return to the main catalog window: {error}")


class CatalogSearchBatch:
  def __init__(self, osver, release, arch, update_type, browser, foreground, use_snapshot_cache=True, prime_update_date=None):
    self.osver = osver
    self.release = release
    self.arch = arch
    self.update_type = update_type
    self.browser = browser
    self.foreground = foreground
    self.use_snapshot_cache = use_snapshot_cache
    self.prime_update_date = prime_update_date
    self.search_index = None
    self.browser_session = _BrowserSession(browser, foreground)

    search_context = _build_search_context(
      osver,
      release,
      arch,
      update_type,
      prime_update_date or '1970-01',
      browser,
      foreground,
      use_snapshot_cache,
    )
    try:
      self.search_index = search_context._load_search_index()
    finally:
      search_context.session.close()

  def resolve(self, update_date):
    search = _build_search_context(
      self.osver,
      self.release,
      self.arch,
      self.update_type,
      update_date,
      self.browser,
      self.foreground,
      self.use_snapshot_cache,
    )
    try:
      if self.use_snapshot_cache:
        snapshot_result = search._load_snapshot_result()
        if snapshot_result:
          search.dl_info_dict = snapshot_result
          search.searchresult = SnapshotSearchResult(snapshot_result['updateID'])
          return search

      if self.search_index:
        search.searchresult = search._find_indexed_searchresult(self.search_index)

      if not search.searchresult:
        search._searchresult()

      if search.searchresult and not search.dl_info_dict:
        with self.browser_session.use() as driver:
          search.driver = driver
          search.owns_driver = False
          search._dlbutton()
          search._dlinfo()
      return search
    finally:
      search.session.close()
      if search.owns_driver and search.driver is not None:
        search.driver.quit()

  def close(self):
    self.browser_session.close()
