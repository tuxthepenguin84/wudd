import json
import logging
import os
import shutil

from .config import load_json_file


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
  csv_file_name = os.path.join(outputs_dir, 'wudd.csv')
  with open(csv_file_name, 'a', encoding='utf-8') as csv_file:
    csv_file.write(f"{data['osver']},{data['release']},{data['arch']},{data['date']},{data['title']},{data['kb']},{data['updateID']},{data['files']},{data['sha1']}\n")
  dedupe_txt(csv_file_name)

  json_file_name = os.path.join(outputs_dir, 'wudd.json')
  json_file_data = load_json_file(json_file_name)
  with open(json_file_name, 'w', encoding='utf-8') as json_file:
    new_json = json_struct(data)
    merged_json = merge_dict(json_file_data, new_json)
    json.dump(merged_json, json_file, indent=2)

  txt_file_name = os.path.join(outputs_dir, 'wudd.txt')
  with open(txt_file_name, 'a', encoding='utf-8') as txt_file:
    txt_file.write(f"{data['osver']} {data['release']} {data['arch']} {data['date']} {data['title']} {data['kb']} {data['updateID']} {data['files']} {data['sha1']}\n")
  dedupe_txt(txt_file_name)

