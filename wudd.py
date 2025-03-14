import argparse
import calendar
from datetime import date, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
import shutil
import sys
import time
import urllib.parse


# Classes
class WUDD():
  def __init__(self, osver, release, arch, update_type, update_date):
    self.osver = osver
    self.release = release
    self.arch = arch
    self.type = update_type
    self.date = update_date
    self._searchterm()
    self.searchurl = f"https://www.catalog.update.microsoft.com/Search.aspx?q={urllib.parse.quote(self.searchterm)}"
    self._driver()
    self._searchresult()
    if self.searchresult:
      self._dlbutton()
      self._dlinfo()
      self.driver.quit()

  def _searchterm(self):
    update_type = {
      'cu': 'Cumulative Update',
      'dcu': 'Dynamic Cumulative Update',
      'cup': 'Cumulative Update Preview',
      'dnet': 'Cumulative Update for .NET Framework 3.5, 4.8 and 4.8.1',
      'dnetp': 'Cumulative Update Preview for .NET Framework 3.5, 4.8 and 4.8.1',
      'custom': None
    }
    if self.type == 'custom':
      logging.error('Custom search terms not available yet')
      sys.exit(0)
    elif self.type in update_type:
      update_string = update_type[self.type]
      self.searchterm = f"{self.date} {update_string} for Windows {self.osver} Version {self.release} for {self.arch}"
    else:
      logging.error(f"Invalid update type: {self.type}")
      sys.exit(1)

  def _driver(self):
    browser_options = Options()
    if not parsed_foreground:
      browser_options.add_argument('--headless')
    if parsed_browser == 'firefox':
      self.driver = webdriver.Firefox(options=browser_options)
    elif parsed_browser == 'chrome':
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
    except Exception as e:
      logging.error(f"An error occurred getting download button: {e}")
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
      self.dl_info_dict = {}
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
    except Exception as e:
      logging.error(f"An error occurred getting download info: {e}")
      sys.exit(1)


# Functions
def dedupe_txt(txt_file_name):
  with open(txt_file_name, 'r') as txt_file:
    unique_lines = txt_file.readlines()
  with open(txt_file_name, 'w') as txt_file:
    txt_file.writelines(list(dict.fromkeys(unique_lines)))


def download_wudd(data):
  logging.info('Beginning download')
  file_download_dir = os.path.join(downloads_dir, data['osver'], data['release'], data['arch'], data['date'])
  if not os.path.exists(file_download_dir):
    logging.debug(f"Creating {file_download_dir} directory")
    os.makedirs(file_download_dir)
  for file_url in data['files']:
    file_name = os.path.basename(file_url)
    file_name_path = os.path.join(file_download_dir, file_name)
    file_index = data['files'].index(file_url)
    msft_sha1 = data['sha1'][file_index]

    # Check if file exists
    logging.info(f"Checking if file exists: {file_name}")
    if os.path.isfile(file_name_path):
      logging.info(f"File found: {file_name_path}")
      if parsed_skipsha1:
        logging.info(f"Skipping sha1: {file_name}")
        continue
      else:
        file_sha1 = sha1_file(file_name_path)
        if file_sha1 == msft_sha1:
          logging.info(f"Hashes match - Downloaded File: {file_sha1} | Hash from Microsoft: {msft_sha1}")
          continue
        else:
          logging.warning(f"Hashes do not match - Downloaded File: {file_sha1} | Hash from Microsoft: {msft_sha1}")
          logging.warning(f"Re-downloading {file_url}")

    try:
      # Get file size
      response_head = requests.head(file_url)
      response_head.raise_for_status()
      content_length = int(response_head.headers.get('Content-Length', 0))
      # GB
      if content_length >= 1073741824:
        file_size = f"{content_length / 1073741824:.2f} GB"
      # MB
      elif content_length >= 1048576:
        file_size = f"{content_length / 1048576:.2f} MB"
      # KB or smaller
      elif content_length >= 1024:
        file_size = f"{content_length // 1024} KB"
      else:
        file_size = f"{content_length} bytes"

      # Download file
      logging.info(f"Downloading: {file_size} - {file_name}")
      response = requests.get(file_url, stream=True)
      response.raise_for_status()
      with open(file_name_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
          if chunk:
            f.write(chunk)
      logging.info(f"Downloaded: {file_size} - {file_name}")
    except requests.exceptions.RequestException as e:
      logging.error(f"An error occurred downloading {file_url}: {str(e)}")
      continue

    if parsed_skipsha1:
      logging.info(f"Skipping sha1: {file_name}")
    else:
      # Calculate SHA1 of downloaded file
      file_sha1 = sha1_file(file_name_path)
      if file_sha1 == msft_sha1:
        logging.info(f"Hashes match - Downloaded File: {file_sha1} | Hash from Microsoft: {msft_sha1}")
      else:
        logging.error(f"Hashes do not match - Downloaded File: {file_sha1} | Hash from Microsoft: {msft_sha1}")
        sys.exit(1)



def get_dates(start_date_dict, end_date_dict):
  start_date = date(start_date_dict['year'], start_date_dict['month'], 1)
  end_date = date(end_date_dict['year'], end_date_dict['month'], 1)
  result = []
  while start_date <= end_date:
    result.append(start_date.strftime('%Y-%m'))
    if start_date.month == 12:
      start_date = date(start_date.year + 1, 1, 1)
    else:
      start_date = date(start_date.year, start_date.month + 1, 1)
  return result


def json_struct(json_data):
  new_json = {
    json_data['osver']: {
      json_data['release']: {
        json_data['arch']: {
          json_data['date']: {
            json_data['updateID']: {
              'title': json_data['title'],
              'kb': json_data['kb'],
              'files': json_data['files'],
              'sha1': json_data['sha1']
            }
          }
        }
      }
    }
  }
  return new_json


def latest_patch_tuesday(year, month):
  second_tuesday = date(year, month, 8)
  while True:
    if calendar.day_name[second_tuesday.weekday()] == 'Tuesday':
      break
    else:
      second_tuesday += timedelta(days=1)
  if second_tuesday > today:
    if month == 1:
      return latest_patch_tuesday(year-1, 12)
    return latest_patch_tuesday(year, month-1)
  return [second_tuesday.strftime("%Y-%m")]


def load_json_file(json_file, import_retries = 5):
  json_data = None
  if Path(json_file).is_file():
    while import_retries > 0 and json_data is None:
      try:
        json_data = json.load(open(Path(json_file)))
        return json_data
      except json.decoder.JSONDecodeError as error:
        logging.error(error)
        time.sleep(1/import_retries)
        import_retries -= 1
  else:
    logging.critical(f"{json_file} is not a file")
  logging.critical(f"Unable to import {json_data} data")
  sys.exit(1)


def merge_dict(dict1, dict2):
  merged = dict1.copy()
  for key in dict2:
    if key in merged and isinstance(merged[key], dict) and isinstance(dict2[key], dict):
      merged[key] = merge_dict(merged[key], dict2[key])
    else:
      merged[key] = dict2.get(key)
  return merged


def print_wudd(data):
  logging.info(f'--------------')
  logging.info(f"OS Version: {data['osver']}")
  logging.info(f"Release: {data['release']}")
  logging.info(f"Arch: {data['arch']}")
  logging.info(f"Date: {data['date']}")
  logging.info(f"Title: {data['title']}")
  logging.info(f"KB: {data['kb']}")
  logging.info(f"UpdateID: {data['updateID']}")
  logging.info(f"Files: {data['files']}")
  logging.info(f"SHA1: {data['sha1']}")


def reset_files():
  if parsed_clean:
    if parsed_download:
      shutil.rmtree(downloads_dir)
    shutil.rmtree(outputs_dir)
  if not os.path.exists(outputs_dir):
    logging.debug(f"Creating {outputs_dir} directory")
    os.makedirs(outputs_dir)
  for file_type in ['.csv', '.json', '.txt']:
    file_path = os.path.join(outputs_dir, f'wudd{file_type}')
    if not os.path.isfile(file_path):
      with open(file_path, 'w') as f:
        if file_type == '.csv':
          f.write('osver,release,arch,date,title,kb,updateID,files,sha1\n')
        elif file_type == '.json':
          json.dump({}, f)
        elif file_type == '.txt':
          f.write('osver release arch date title kb updateID files sha1\n')


def save_wudd(data):
  # CSV
  csv_file_name = os.path.join(outputs_dir, 'wudd.csv')
  with open(csv_file_name, 'a') as csv_file:
    csv_file.write(f"{data['osver']},{data['release']},{data['arch']},{data['date']},{data['title']},{data['kb']},{data['updateID']},{data['files']},{data['sha1']}\n")
  dedupe_txt(csv_file_name)

  # JSON
  json_file_name = os.path.join(outputs_dir, 'wudd.json')
  json_file_data = load_json_file(json_file_name)
  with open(json_file_name, 'w') as json_file:
    new_json = json_struct(data)
    merged_json = merge_dict(json_file_data, new_json)
    json.dump(merged_json, json_file, indent=2)

  # TXT
  txt_file_name = os.path.join(outputs_dir, 'wudd.txt')
  with open(txt_file_name, 'a') as txt_file:
    txt_file.write(f"{data['osver']} {data['release']} {data['arch']} {data['date']} {data['title']} {data['kb']} {data['updateID']} {data['files']} {data['sha1']}\n")
  dedupe_txt(txt_file_name)


def sha1_file(file_name_path):
  file_name = os.path.basename(file_name_path)
  logging.info(f"Calculating sha1: {file_name}")
  file_sha1 = hashlib.sha1()
  buf_size = 65536
  with open(file_name_path, 'rb') as f:
    while True:
      file_data = f.read(buf_size)
      if not file_data:
        break
      file_sha1.update(file_data)
  file_sha1 = file_sha1.hexdigest()
  logging.info(f"Downloaded file sha1: {file_sha1}")
  return file_sha1


def main():
  reset_files()
  for osver in os_json:
    releases = os_json[osver]['releases']
    for release in releases:
      arches = releases[release]['archs']
      for arch in arches:
        update_types = arches[arch]['ut']
        for update_type in update_types:
          if parsed_latest:
            update_dates = latest_patch_tuesday(year, month)
          else:
            update_dates = get_dates(arches[arch]['start'], arches[arch]['end'])
          for update_date in update_dates:
            logging.debug(f"{osver} {release} {arch} {update_date}")
            wudd = WUDD(osver, release, arch, update_type, update_date)
            if wudd.searchresult:
              print_wudd(wudd.dl_info_dict)
              save_wudd(wudd.dl_info_dict)
              if parsed_download:
                download_wudd(wudd.dl_info_dict)


if __name__ == '__main__':
  # Import OS JSON data
  local_dir = os.path.dirname(os.path.abspath(__file__))
  os_file = os.path.join(local_dir, 'osinfo.json')
  os_json = load_json_file(os_file)

  # Arg Parser
  arg_parser = argparse.ArgumentParser(description='Windows Update Direct Download')
  arg_parser.add_argument('--browser', help='Browser to use', choices=['chrome', 'firefox'], default='chrome')
  arg_parser.add_argument('--clean', help='Clean downloads and outputs dirs before starting', action='store_true', default=False)
  arg_parser.add_argument('--download', help='Download updates', action='store_true', default=False)
  arg_parser.add_argument('--foreground', help='Run browser in the foreground', action='store_true', default=False)
  arg_parser.add_argument('--latest', help='Only pulls the latest updates, ignores start/end dates', action='store_true', default=False)
  arg_parser.add_argument('--logging', help='Log level', choices=['debug', 'info', 'warning', 'error', 'critical'], default='info')
  arg_parser.add_argument('--skipsha1', help='Skip sha1 hash check', action='store_true', default=False)
  parsed_args = arg_parser.parse_args()
  parsed_browser = parsed_args.browser
  parsed_clean = parsed_args.clean
  parsed_download = parsed_args.download
  parsed_foreground = parsed_args.foreground
  parsed_latest = parsed_args.latest
  parsed_logging = parsed_args.logging
  parsed_skipsha1 = parsed_args.skipsha1

  if parsed_browser == 'chrome':
    from selenium.webdriver.chrome.options import Options
  elif parsed_browser == 'firefox':
    from selenium.webdriver.firefox.options import Options

  downloads_dir = os.path.join(local_dir, 'downloads')
  outputs_dir = os.path.join(local_dir, 'outputs')

  today = date.today()
  year = today.year
  month = today.month

  # Logging Config
  logging.basicConfig(
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=getattr(logging, parsed_logging.upper()),
  )
  logging.debug(parsed_args)

  # Begin main() loop
  main()