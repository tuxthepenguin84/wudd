from concurrent.futures import ThreadPoolExecutor, as_completed

from .catalog import CatalogSearchBatch
from .catalog import create_browser_session_pool
from .config import get_dates, latest_patch_tuesday, resolve_year_month
from .downloads import download_wudd
from .outputs import print_wudd, reset_files, save_wudd


def _run_parallel(items, workers, function):
  if workers == 1 or len(items) <= 1:
    return [function(item) for item in items]

  results = [None] * len(items)
  with ThreadPoolExecutor(max_workers=min(workers, len(items))) as executor:
    futures = {executor.submit(function, item): index for index, item in enumerate(items)}
    for future in as_completed(futures):
      results[futures[future]] = future.result()
  return results


def _persist_wudd(wudd, config):
  if not wudd.searchresult:
    return
  print_wudd(wudd.dl_info_dict)
  save_wudd(wudd.dl_info_dict, config.outputs_dir)
  return wudd.dl_info_dict


def _update_dates_for_type(update_type, update_dates):
  if update_type == 'cup' and update_dates:
    return [update_dates[-1]]
  return list(update_dates)


def _resolve_update_type(task, config, browser_session_pool, workers):
  osver, release, arch, update_type, update_dates = task
  update_dates = _update_dates_for_type(update_type, update_dates)
  batch = CatalogSearchBatch(
    osver,
    release,
    arch,
    update_type,
    config.browser,
    config.foreground,
    getattr(config, 'use_snapshot_cache', True),
    prime_update_date=update_dates[0] if update_dates else None,
    browser_pool_size=workers,
    browser_session_pool=browser_session_pool,
  )
  try:
    discovered = _run_parallel(update_dates, workers, batch.discover)
    finalized = _run_parallel(discovered, workers, batch.finalize)
    return [wudd for wudd in finalized if wudd.searchresult]
  finally:
    batch.close()


def run(os_json, config):
  reset_files(config.downloads_dir, config.outputs_dir, config.clean, config.download)
  workers = max(1, getattr(config, 'workers', 1))
  browser_session_pool = create_browser_session_pool(config.browser, config.foreground, workers)
  try:
    update_type_jobs = []
    for osver in os_json:
      releases = os_json[osver]['releases']
      for release in releases:
        arches = releases[release]['archs']
        for arch in arches:
          update_types = arches[arch]['ut']
          if config.latest:
            update_dates = latest_patch_tuesday(config.today)
          else:
            start_date = resolve_year_month(arches[arch]['start'], config.today)
            end_date = resolve_year_month(arches[arch]['end'], config.today)
            update_dates = get_dates(start_date, end_date)
          if not update_dates:
            continue
          for update_type in update_types:
            update_type_jobs.append((osver, release, arch, update_type, list(update_dates)))

    finalized = _run_parallel(
      update_type_jobs,
      workers,
      lambda task: _resolve_update_type(task, config, browser_session_pool, workers),
    )
    download_jobs = []
    for wudd in [item for group in finalized for item in group]:
      download_jobs.append(_persist_wudd(wudd, config))

    if config.download:
      download_jobs = [job for job in download_jobs if job]
      _run_parallel(
        download_jobs,
        workers,
        lambda data: download_wudd(data, config.downloads_dir, config.skipsha1),
      )
  finally:
    browser_session_pool.close()
