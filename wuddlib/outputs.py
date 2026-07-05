import csv
import json
import logging
import os
import shutil

from .config import load_data_file


CSV_FIELDS = ['osver', 'release', 'arch', 'date', 'title', 'kb', 'updateID', 'files', 'sha1']
ARCH_SORT_ORDER = {
  'x64': 0,
  'arm64': 1,
  'x86': 2,
}
UPDATE_TYPE_SORT_ORDER = {
  'cu': 0,
  'dcu': 1,
  'cup': 2,
  'dnet': 3,
}


def dedupe_txt(txt_file_name):
  with open(txt_file_name, 'r', encoding='utf-8') as txt_file:
    unique_lines = txt_file.readlines()
  with open(txt_file_name, 'w', encoding='utf-8') as txt_file:
    txt_file.writelines(list(dict.fromkeys(unique_lines)))


def merge_dict(dict1, dict2):
  merged = dict1.copy()
  for key in dict2:
    if key in merged and isinstance(merged[key], dict) and isinstance(dict2[key], dict):
      merged[key] = merge_dict(merged[key], dict2[key])
    else:
      merged[key] = dict2.get(key)
  return merged


def json_struct(json_data):
  return {
    json_data['osver']: {
      json_data['release']: {
        json_data['arch']: {
          json_data['date']: {
            json_data['updateID']: {
              'title': json_data['title'],
              'kb': json_data['kb'],
              'files': json_data['files'],
              'sha1': json_data['sha1'],
            }
          }
        }
      }
    }
  }


def infer_update_type(title):
  lowered_title = title.lower()
  if '.net framework' in lowered_title:
    return 'dnet'
  if 'dynamic cumulative update' in lowered_title:
    return 'dcu'
  if 'preview' in lowered_title:
    return 'cup'
  return 'cu'


def osver_sort_key(osver):
  if str(osver).isdigit():
    return (0, int(osver))
  return (1, str(osver))


def arch_sort_key(arch):
  return (ARCH_SORT_ORDER.get(arch, 99), arch)


def update_type_sort_key(title):
  return UPDATE_TYPE_SORT_ORDER.get(infer_update_type(title), 99)


def sort_output_tree(data):
  sorted_tree = {}
  for osver in sorted(data, key=osver_sort_key):
    sorted_tree[osver] = {}
    for release in sorted(data[osver]):
      sorted_tree[osver][release] = {}
      for arch in sorted(data[osver][release], key=arch_sort_key):
        sorted_tree[osver][release][arch] = {}
        for date_key in sorted(data[osver][release][arch]):
          records = data[osver][release][arch][date_key]
          sorted_tree[osver][release][arch][date_key] = {}
          for update_id, record in sorted(
            records.items(),
            key=lambda item: (
              update_type_sort_key(item[1]['title']),
              item[1]['title'],
              item[0],
            ),
          ):
            sorted_tree[osver][release][arch][date_key][update_id] = record
  return sorted_tree


def iter_output_rows(data):
  for osver in sorted(data, key=osver_sort_key):
    for release in sorted(data[osver]):
      for arch in sorted(data[osver][release], key=arch_sort_key):
        for date_key in sorted(data[osver][release][arch]):
          for update_id, record in sorted(
            data[osver][release][arch][date_key].items(),
            key=lambda item: (
              update_type_sort_key(item[1]['title']),
              item[1]['title'],
              item[0],
            ),
          ):
            yield {
              'osver': osver,
              'release': release,
              'arch': arch,
              'date': date_key,
              'title': record['title'],
              'kb': record['kb'],
              'updateID': update_id,
              'files': record['files'],
              'sha1': record['sha1'],
            }


def write_output_files(outputs_dir, data):
  sorted_data = sort_output_tree(data)
  rows = list(iter_output_rows(sorted_data))

  json_file_name = os.path.join(outputs_dir, 'wudd.json')
  with open(json_file_name, 'w', encoding='utf-8') as json_file:
    json.dump(sorted_data, json_file, indent=2)

  csv_file_name = os.path.join(outputs_dir, 'wudd.csv')
  with open(csv_file_name, 'w', encoding='utf-8', newline='') as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)

  txt_file_name = os.path.join(outputs_dir, 'wudd.txt')
  with open(txt_file_name, 'w', encoding='utf-8') as txt_file:
    txt_file.write('osver release arch date title kb updateID files sha1\n')
    for row in rows:
      txt_file.write(f"{row['osver']} {row['release']} {row['arch']} {row['date']} {row['title']} {row['kb']} {row['updateID']} {row['files']} {row['sha1']}\n")


def print_wudd(data):
  logging.info('--------------')
  logging.info(f"OS Version: {data['osver']}")
  logging.info(f"Release: {data['release']}")
  logging.info(f"Arch: {data['arch']}")
  logging.info(f"Date: {data['date']}")
  logging.info(f"Title: {data['title']}")
  logging.info(f"KB: {data['kb']}")
  logging.info(f"UpdateID: {data['updateID']}")
  logging.info(f"Files: {data['files']}")
  logging.info(f"SHA1: {data['sha1']}")


def reset_files(downloads_dir, outputs_dir, clean, download):
  if clean:
    if download and os.path.exists(downloads_dir):
      shutil.rmtree(downloads_dir)
    if os.path.exists(outputs_dir):
      shutil.rmtree(outputs_dir)
  os.makedirs(outputs_dir, exist_ok=True)
  for file_type in ['.csv', '.json', '.txt']:
    file_path = os.path.join(outputs_dir, f'wudd{file_type}')
    if not os.path.isfile(file_path):
      with open(file_path, 'w', encoding='utf-8') as file_handle:
        if file_type == '.csv':
          file_handle.write('osver,release,arch,date,title,kb,updateID,files,sha1\n')
        elif file_type == '.json':
          json.dump({}, file_handle)
        elif file_type == '.txt':
          file_handle.write('osver release arch date title kb updateID files sha1\n')


def save_wudd(data, outputs_dir):
  json_file_name = os.path.join(outputs_dir, 'wudd.json')
  json_file_data = load_data_file(json_file_name)
  new_json = json_struct(data)
  merged_json = merge_dict(json_file_data, new_json)
  write_output_files(outputs_dir, merged_json)
