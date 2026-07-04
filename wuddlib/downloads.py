import hashlib
import logging
import os
import sys

import requests


def sha1_file(file_name_path):
  file_name = os.path.basename(file_name_path)
  logging.info(f"Calculating sha1: {file_name}")
  file_sha1 = hashlib.sha1()
  buf_size = 65536
  with open(file_name_path, 'rb') as file_handle:
    while True:
      file_data = file_handle.read(buf_size)
      if not file_data:
        break
      file_sha1.update(file_data)
  file_sha1 = file_sha1.hexdigest()
  logging.info(f"Downloaded file sha1: {file_sha1}")
  return file_sha1


def download_wudd(data, downloads_dir, skipsha1):
  logging.info('Beginning download')
  file_download_dir = os.path.join(downloads_dir, data['osver'], data['release'], data['arch'], data['date'])
  os.makedirs(file_download_dir, exist_ok=True)

  for file_index, file_url in enumerate(data['files']):
    file_name = os.path.basename(file_url)
    file_name_path = os.path.join(file_download_dir, file_name)
    msft_sha1 = data['sha1'][file_index]

    logging.info(f"Checking if file exists: {file_name}")
    if os.path.isfile(file_name_path):
      logging.info(f"File found: {file_name_path}")
      if skipsha1:
        logging.info(f"Skipping sha1: {file_name}")
        continue

      file_sha1 = sha1_file(file_name_path)
      if file_sha1 == msft_sha1:
        logging.info(f"Hashes match - Downloaded File: {file_sha1} | Hash from Microsoft: {msft_sha1}")
        continue

      logging.warning(f"Hashes do not match - Downloaded File: {file_sha1} | Hash from Microsoft: {msft_sha1}")
      logging.warning(f"Re-downloading {file_url}")

    try:
      response_head = requests.head(file_url)
      response_head.raise_for_status()
      content_length = int(response_head.headers.get('Content-Length', 0))
      if content_length >= 1073741824:
        file_size = f"{content_length / 1073741824:.2f} GB"
      elif content_length >= 1048576:
        file_size = f"{content_length / 1048576:.2f} MB"
      elif content_length >= 1024:
        file_size = f"{content_length // 1024} KB"
      else:
        file_size = f"{content_length} bytes"

      logging.info(f"Downloading: {file_size} - {file_name}")
      response = requests.get(file_url, stream=True)
      response.raise_for_status()
      with open(file_name_path, 'wb') as file_handle:
        for chunk in response.iter_content(chunk_size=8192):
          if chunk:
            file_handle.write(chunk)
      logging.info(f"Downloaded: {file_size} - {file_name}")
    except requests.exceptions.RequestException as error:
      logging.error(f"An error occurred downloading {file_url}: {str(error)}")
      continue

    if skipsha1:
      logging.info(f"Skipping sha1: {file_name}")
      continue

    file_sha1 = sha1_file(file_name_path)
    if file_sha1 == msft_sha1:
      logging.info(f"Hashes match - Downloaded File: {file_sha1} | Hash from Microsoft: {msft_sha1}")
    else:
      logging.error(f"Hashes do not match - Downloaded File: {file_sha1} | Hash from Microsoft: {msft_sha1}")
      sys.exit(1)
