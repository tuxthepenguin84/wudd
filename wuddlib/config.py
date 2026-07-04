from dataclasses import dataclass, field
from datetime import date, timedelta
import calendar
import json
import logging
import sys
import time
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
  browser: str
  clean: bool
  download: bool
  foreground: bool
  latest: bool
  log_level: str
  skipsha1: bool
  local_dir: str
  downloads_dir: str
  outputs_dir: str
  today: date = field(default_factory=date.today)


def load_json_file(json_file, import_retries=5):
  json_data = None
  if Path(json_file).is_file():
    while import_retries > 0 and json_data is None:
      try:
        with open(Path(json_file), encoding='utf-8') as file_handle:
          json_data = json.load(file_handle)
        return json_data
      except json.decoder.JSONDecodeError as error:
        logging.error(error)
        time.sleep(1 / import_retries)
        import_retries -= 1
  else:
    logging.critical(f"{json_file} is not a file")
  logging.critical(f"Unable to import {json_data} data")
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


def latest_patch_tuesday(today_value):
  year = today_value.year
  month = today_value.month

  while True:
    second_tuesday = date(year, month, 8)
    while calendar.day_name[second_tuesday.weekday()] != 'Tuesday':
      second_tuesday += timedelta(days=1)
    if second_tuesday <= today_value:
      return [second_tuesday.strftime('%Y-%m')]
    if month == 1:
      year -= 1
      month = 12
    else:
      month -= 1
