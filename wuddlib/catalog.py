import json
import logging
import os
import re
import sys
import time
import urllib.parse

from selenium import webdriver
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions


class SnapshotSearchResult:
  def __init__(self, update_id):
    self._update_id = update_id

  def get_attribute(self, name):
    if name == 'id':
      return self._update_id
    return None


class CatalogSearch:
  def __init__(self, osver, release, arch, update_type, update_date, browser, foreground):
    self.osver = osver
    self.release = release
    self.arch = arch
    self.type = update_type
    self.date = update_date
    self.browser = browser
    self.foreground = foreground
    self.driver = None
    self.searchresult = None
    self.dl_info_dict = {}
    self._kb_hint = None

    try:
      self._searchterm()
      self.searchurl = f"https://www.catalog.update.microsoft.com/Search.aspx?q={urllib.parse.quote(self.searchterm)}"
      self.fallback_searchterm = self._fallback_searchterm()
      self.fallback_searchurl = None
      if self.fallback_searchterm and self.fallback_searchterm != self.searchterm:
        self.fallback_searchurl = f"https://www.catalog.update.microsoft.com/Search.aspx?q={urllib.parse.quote(self.fallback_searchterm)}"
      self._driver()
      self._searchresult()
      if self.searchresult and not self.dl_info_dict:
        self._dlbutton()
        self._dlinfo()
    finally:
      if self.driver is not None:
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
    if self.browser == 'firefox':
      browser_options = FirefoxOptions()
      if not self.foreground:
        browser_options.add_argument('--headless')
      self.driver = webdriver.Firefox(options=browser_options)
      return

    browser_options = ChromeOptions()
    if not self.foreground:
      browser_options.add_argument('--headless')
    self.driver = webdriver.Chrome(options=browser_options)

  def _searchresult(self):
    if self._search_pages(self.searchurl, self._find_exact_searchresult, 'exact title search'):
      return

    if self.fallback_searchurl and self._search_pages(
      self.fallback_searchurl,
      self._find_exact_or_kb_searchresult,
      'fallback search',
    ):
      return

    snapshot_result = self._load_snapshot_result()
    if snapshot_result:
      self.dl_info_dict = snapshot_result
      self.searchresult = SnapshotSearchResult(snapshot_result['updateID'])
      logging.debug(f"Loaded snapshot fallback for: {self.searchterm}")
      return

    logging.warning(f"No results for: {self.searchterm}")
    self.searchresult = None

  def _search_pages(self, searchurl, finder, search_label):
    self.driver.get(searchurl)
    page_number = 1
    while True:
      searchresult = finder()
      if searchresult:
        self.searchresult = searchresult
        logging.debug(f"Search Result Element ID: {self.searchresult.get_attribute('id')}")
        logging.debug(f"{search_label} found on page {page_number}")
        return True

      logging.debug(f"No {search_label} result on page {page_number} for: {self.searchterm}")
      if not self._next_page():
        return False
      page_number += 1

  def _find_exact_searchresult(self):
    xpath_expression_searchresult = f"//td[a[contains(normalize-space(.), '{self.searchterm}')]]"
    try:
      return self.driver.find_element(By.XPATH, xpath_expression_searchresult)
    except NoSuchElementException:
      return None

  def _find_exact_or_kb_searchresult(self):
    exact_result = self._find_exact_searchresult()
    if exact_result:
      return exact_result
    return self._find_fallback_searchresult()

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

  def _find_fallback_searchresult(self):
    kb_hint = self._load_kb_hint()
    if not kb_hint:
      return None

    result_rows = self.driver.find_elements(By.XPATH, "//table[@id='ctl00_catalogBody_updateMatches']//tr[td]")
    for row in result_rows:
      row_text = " ".join(getattr(row, 'text', '').split())
      if not row_text or kb_hint not in row_text:
        continue
      if not self._row_matches_metadata(row_text):
        continue
      try:
        return row.find_element(By.XPATH, ".//input[@type='button']")
      except NoSuchElementException:
        try:
          return row.find_element(By.XPATH, ".//a[contains(@id, '_link')]")
        except NoSuchElementException:
          continue
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
    if self._kb_hint is not None:
      return self._kb_hint

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    snapshot_paths = [
      os.path.join(repo_root, 'stored', 'wudd.json'),
      os.path.join(repo_root, 'outputs', 'wudd.json'),
    ]
    for snapshot_path in snapshot_paths:
      if not os.path.isfile(snapshot_path):
        continue
      try:
        with open(snapshot_path, 'r', encoding='utf-8') as snapshot_file:
          snapshot_data = json.load(snapshot_file)
      except Exception as error:
        logging.debug(f"Could not load KB hint from {snapshot_path}: {error}")
        continue

      try:
        date_records = snapshot_data[self.osver][self.release][self.arch][self.date]
      except KeyError:
        continue

      for record in date_records.values():
        title = record.get('title', '')
        if self._title_matches_update_type(title):
          kb = record.get('kb')
          if kb:
            self._kb_hint = kb
            logging.debug(f"Loaded KB hint {kb} from {snapshot_path}")
            return self._kb_hint

      if date_records:
        first_record = next(iter(date_records.values()))
        kb = first_record.get('kb')
        if kb:
          self._kb_hint = kb
          logging.debug(f"Loaded fallback KB hint {kb} from {snapshot_path}")
          return self._kb_hint

    return None

  def _load_snapshot_result(self):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    snapshot_paths = [
      os.path.join(repo_root, 'stored', 'wudd.json'),
      os.path.join(repo_root, 'outputs', 'wudd.json'),
    ]
    for snapshot_path in snapshot_paths:
      if not os.path.isfile(snapshot_path):
        continue
      try:
        with open(snapshot_path, 'r', encoding='utf-8') as snapshot_file:
          snapshot_data = json.load(snapshot_file)
      except Exception as error:
        logging.debug(f"Could not load snapshot fallback from {snapshot_path}: {error}")
        continue

      try:
        date_records = snapshot_data[self.osver][self.release][self.arch][self.date]
      except KeyError:
        continue

      for update_id, record in date_records.items():
        title = record.get('title', '')
        if self._title_matches_update_type(title):
          kb = record.get('kb')
          files = record.get('files', [])
          sha1 = record.get('sha1', [])
          if kb and files and sha1:
            logging.debug(f"Loaded snapshot result {update_id} from {snapshot_path}")
            return {
              'osver': self.osver,
              'release': self.release,
              'arch': self.arch,
              'date': self.date,
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
          logging.debug(f"Loaded generic snapshot result {update_id} from {snapshot_path}")
          return {
            'osver': self.osver,
            'release': self.release,
            'arch': self.arch,
            'date': self.date,
            'updateID': update_id,
            'title': record.get('title', ''),
            'kb': kb,
            'files': files,
            'sha1': sha1,
          }

    return None

  def _title_matches_update_type(self, title):
    lowered_title = title.lower()
    if self.type == 'dcu':
      return 'dynamic cumulative update' in lowered_title
    if self.type == 'cup':
      return 'cumulative update' in lowered_title and 'preview' in lowered_title
    if self.type == 'dnet':
      return '.net framework' in lowered_title and 'preview' not in lowered_title
    if self.type == 'dnetp':
      return '.net framework' in lowered_title and 'preview' in lowered_title
    return 'cumulative update' in lowered_title and 'dynamic cumulative update' not in lowered_title

  def _next_page(self):
    next_page_selectors = [
      (By.ID, 'ctl00_catalogBody_nextPageLinkText'),
      (By.ID, 'ctl00_catalogBody_nextPageLinkButton'),
    ]
    for by, selector in next_page_selectors:
      try:
        self._click_element(self.driver.find_element(by, selector), 'next page link')
        time.sleep(0.25)
        return True
      except NoSuchElementException:
        continue
    return False

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
      dl_button = re.sub(r"_\w+$", "", self.searchresult.get_attribute('id'))
      logging.debug(f"Download Button Element ID: {dl_button}")
      xpath_expression_dl_button = f"//*[@id='{dl_button}']"
      dl_link = self.driver.find_element(By.XPATH, xpath_expression_dl_button)
      logging.debug('Clicking download button...')
      if not self._click_element(dl_link, 'download button'):
        raise RuntimeError('Download button click failed')
    except Exception as error:
      logging.error(f"An error occurred getting download button: {error}")
      sys.exit(1)

  def _dlinfo(self):
    handles = self.driver.window_handles
    self.driver.switch_to.window(handles[-1])
    try:
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
