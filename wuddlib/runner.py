from .catalog import CatalogSearch
from .config import get_dates, latest_patch_tuesday
from .downloads import download_wudd
from .outputs import print_wudd, reset_files, save_wudd


def run(os_json, config):
  reset_files(config.downloads_dir, config.outputs_dir, config.clean, config.download)
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
          for update_date in update_dates:
            wudd = CatalogSearch(
              osver,
              release,
              arch,
              update_type,
              update_date,
              config.browser,
              config.foreground,
            )
            if wudd.searchresult:
              print_wudd(wudd.dl_info_dict)
              save_wudd(wudd.dl_info_dict, config.outputs_dir)
              if config.download:
                download_wudd(wudd.dl_info_dict, config.downloads_dir, config.skipsha1)

