from dataclasses import dataclass, field
from datetime import date, timedelta
import calendar
import json
import logging
import sys
import time
from pathlib import Path
import tomllib

LATEST_MONTH_SENTINELS = {
  'latest',
  'latest-patch-tuesday',
  'latest_patch_tuesday',
  'patch-tuesday',
  'patch_tuesday',
}


@dataclass(frozen=True)
class AppConfig:
  browser: str
  clean: bool
  download: bool
  foreground: bool
  latest: bool
  log_level: str
  skipsha1: bool
  workers: int
  use_snapshot_cache: bool
  local_dir: str
  downloads_dir: str
  outputs_dir: str
  today: date = field(default_factory=date.today)


def _parse_year_month(value, allow_latest=False):
  if isinstance(value, dict):
    return value
  if isinstance(value, str):
    normalized = value.strip().lower()
    if allow_latest and normalized in LATEST_MONTH_SENTINELS:
      return normalized
    year, month = value.split('-')
    return {'year': int(year), 'month': int(month)}
  raise ValueError(f'Unsupported year-month value: {value!r}')


def _as_list(value):
  if isinstance(value, (list, tuple)):
    return list(value)
  return [value]


def _pick_sequence_value(values, index, label):
  if len(values) == 1:
    return values[0]
  if len(values) <= index:
    raise ValueError(f'{label} list must either contain one item or match the release list length')
  return values[index]


def _normalize_release_entries(target):
  releases_value = target.get('releases', target.get('release'))
  if isinstance(releases_value, dict):
    release_entries = []
    for release, release_value in releases_value.items():
      if isinstance(release_value, dict):
        start_value = release_value.get('start', release_value.get('starts', target.get('start')))
        end_value = release_value.get('end', release_value.get('ends', target.get('end', 'latest_patch_tuesday')))
      else:
        start_value = release_value
        end_value = target.get('end', 'latest_patch_tuesday')
      release_entries.append((str(release), start_value, end_value))
    return release_entries

  release_values = _as_list(releases_value)
  start_values = _as_list(target.get('starts', target.get('start')))
  end_values = _as_list(target.get('ends', target.get('end', 'latest_patch_tuesday')))
  if len(start_values) not in {1, len(release_values)}:
    raise ValueError('start list must either contain one item or match the release list length')
  if len(end_values) not in {1, len(release_values)}:
    raise ValueError('end list must either contain one item or match the release list length')
  return [
    (
      str(release_value),
      _pick_sequence_value(start_values, index, 'start'),
      _pick_sequence_value(end_values, index, 'end'),
    )
    for index, release_value in enumerate(release_values)
  ]


def _normalize_config_data(file_data):
  if isinstance(file_data, dict) and 'targets' in file_data:
    nested_config = {}
    for target in file_data['targets']:
      osver = str(target['os'])
      arch_values = _as_list(target.get('archs', target.get('arch')))
      release_entries = _normalize_release_entries(target)

      nested_config.setdefault(osver, {'releases': {}})
      for index, (release, start_value, end_value) in enumerate(release_entries):
        start = _parse_year_month(start_value)
        end = _parse_year_month(end_value, allow_latest=True)
        nested_config[osver]['releases'].setdefault(release, {'archs': {}})
        for arch_value in arch_values:
          arch = str(arch_value)
          nested_config[osver]['releases'][release]['archs'][arch] = {
            'ut': list(target.get('updates', [])),
            'start': start,
            'end': end,
          }
    return nested_config
  return file_data


def load_data_file(data_file, import_retries=5):
  file_data = None
  data_file = Path(data_file)
  if data_file.is_file():
    while import_retries > 0 and file_data is None:
      try:
        if data_file.suffix.lower() == '.toml':
          with open(data_file, 'rb') as file_handle:
            file_data = tomllib.load(file_handle)
        else:
          with open(data_file, encoding='utf-8') as file_handle:
            file_data = json.load(file_handle)
        if file_data is None:
          raise ValueError(f'{data_file} is empty')
        return _normalize_config_data(file_data)
      except (json.decoder.JSONDecodeError, OSError, tomllib.TOMLDecodeError, ValueError, KeyError, TypeError) as error:
        logging.error(error)
        time.sleep(1 / import_retries)
        import_retries -= 1
  else:
    logging.critical(f"{data_file} is not a file")
  logging.critical(f"Unable to import {file_data} data")
  sys.exit(1)


load_json_file = load_data_file


def resolve_year_month(value, today_value=None):
  if isinstance(value, dict):
    return value
  if isinstance(value, str):
    normalized = value.strip().lower()
    if normalized in LATEST_MONTH_SENTINELS:
      if today_value is None:
        today_value = date.today()
      latest_month = latest_patch_tuesday(today_value)[0]
      year, month = latest_month.split('-')
      return {'year': int(year), 'month': int(month)}
    year, month = value.split('-')
    return {'year': int(year), 'month': int(month)}
  raise ValueError(f'Unsupported year-month value: {value!r}')


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
