import argparse
import logging
import os

from wuddlib.config import AppConfig, load_json_file


def build_parser():
  arg_parser = argparse.ArgumentParser(description='Windows Update Direct Download')
  arg_parser.add_argument('--browser', help='Browser to use', choices=['chrome', 'firefox'], default='chrome')
  arg_parser.add_argument('--clean', help='Clean downloads and outputs dirs before starting', action='store_true', default=False)
  arg_parser.add_argument('--download', help='Download updates', action='store_true', default=False)
  arg_parser.add_argument('--foreground', help='Run browser in the foreground', action='store_true', default=False)
  arg_parser.add_argument('--latest', help='Only pulls the latest updates, ignores start/end dates', action='store_true', default=False)
  arg_parser.add_argument('--logging', help='Log level', choices=['debug', 'info', 'warning', 'error', 'critical'], default='info')
  arg_parser.add_argument('--skipsha1', help='Skip sha1 hash check', action='store_true', default=False)
  return arg_parser


def main():
  parsed_args = build_parser().parse_args()

  logging.basicConfig(
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=getattr(logging, parsed_args.logging.upper()),
  )

  local_dir = os.path.dirname(os.path.abspath(__file__))
  os_file = os.path.join(local_dir, 'osinfo.json')
  os_json = load_json_file(os_file)

  config = AppConfig(
    browser=parsed_args.browser,
    clean=parsed_args.clean,
    download=parsed_args.download,
    foreground=parsed_args.foreground,
    latest=parsed_args.latest,
    log_level=parsed_args.logging,
    skipsha1=parsed_args.skipsha1,
    local_dir=local_dir,
    downloads_dir=os.path.join(local_dir, 'downloads'),
    outputs_dir=os.path.join(local_dir, 'outputs'),
  )

  logging.debug(parsed_args)

  from wuddlib.runner import run

  run(os_json, config)


if __name__ == '__main__':
  main()
