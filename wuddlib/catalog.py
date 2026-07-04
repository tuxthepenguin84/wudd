import logging
import re
import sys
import time
import urllib.parse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions


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

    try:
      self._searchterm()
      self.searchurl = f"https://www.catalog.update.microsoft.com/Search.aspx?q={urllib.parse.quote(self.searchterm)}"
      self._driver()
      self._searchresult()
      if self.searchresult:
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
    self.driver.get(self.searchurl)
    xpath_expression_searchresult = f"//td[a[contains(text(), '{self.searchterm}')]]"
    try:
      self.searchresult = self.driver.find_element(By.XPATH, xpath_expression_searchresult)
      logging.debug(f"Search Result Element ID: {self.searchresult.get_attribute('id')}")
    except Exception:
      logging.warning(f"No results for: {self.searchterm}")
      self.searchresult = None

  def _dlbutton(self):
    try:
      dl_button = re.sub(r"_\w+$", "", self.searchresult.get_attribute('id'))
      logging.debug(f"Download Button Element ID: {dl_button}")
      xpath_expression_dl_button = f"//*[@id='{dl_button}']"
      dl_link = self.driver.find_element(By.XPATH, xpath_expression_dl_button)
      logging.debug('Clicking download button...')
      dl_link.click()
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

