from concurrent.futures import ThreadPoolExecutor, as_completed

from .catalog import CatalogSearchBatch
from .config import get_dates, latest_patch_tuesday
from .downloads import download_wudd
from .outputs import print_wudd, reset_files, save_wudd


def _persist_wudd(wudd, config):
  if not wudd.searchresult:
    return
  print_wudd(wudd.dl_info_dict)
  save_wudd(wudd.dl_info_dict, config.outputs_dir)
  if config.download:
    download_wudd(wudd.dl_info_dict, config.downloads_dir, config.skipsha1)


def run(os_json, config):
  reset_files(config.downloads_dir, config.outputs_dir, config.clean, config.download)
  workers = max(1, getattr(config, 'workers', 1))
  for osver in os_json:
    releases = os_json[osver]['releases']
    for release in releases:
      arches = releases[release]['archs']
      for arch in arches:
        update_types = arches[arch]['ut']
        if config.latest:
          update_dates = latest_patch_tuesday(config.today)
        else:
          update_dates = get_dates(arches[arch]['start'], arches[arch]['end'])
        for update_type in update_types:
          if not update_dates:
            continue
          batch = CatalogSearchBatch(
            osver,
            release,
            arch,
            update_type,
            config.browser,
            config.foreground,
            getattr(config, 'use_snapshot_cache', True),
            prime_update_date=update_dates[0],
          )
          try:
            if workers == 1 or len(update_dates) == 1:
              for update_date in update_dates:
                _persist_wudd(batch.resolve(update_date), config)
              continue

            with ThreadPoolExecutor(max_workers=min(workers, len(update_dates))) as executor:
              futures = [executor.submit(batch.resolve, update_date) for update_date in update_dates]
              for future in as_completed(futures):
                _persist_wudd(future.result(), config)
          finally:
            batch.close()
