# Changelogs

## Latest Changes

## 0.0.1

### :sparkles: Features

- :dart: feat: update ddeutil and use lazy from core instead. (_2024-05-26_)
- :dart: feat: add task for load csv to parquet. (_2024-05-26_)
- :dart: feat: fist implement formatter object to dataset searching. (_2024-05-25_)
- :dart: feat: add loader object that will use yaml config file instead SimLoad. (_2024-05-24_)
- :dart: feat: add workflow config file for use instead params obj. (_2024-05-24_)
- :dart: feat: add task regex for searching task value. (_2024-05-24_)
- :dart: feat: add extras model for CSV on polars dataframe. (_2024-05-23_)
- :dart: feat: add conn model on dataset field. (_2024-05-23_)
- :dart: feat: add catching output from shell stage. (_2024-05-23_)
- :dart: feat: add execute for shell stage. (_2024-05-22_)
- :dart: feat: add callable type on caller. (_2024-05-22_)
- :dart: feat: add locals to exec python statement together with globals. (_2024-05-22_)
- :dart: feat: add map caller function to stage. (_2024-05-22_)
- :dart: feat: add shell stage on stags object. (_2024-05-21_)
- :dart: feat: add execute method on pipeline. (_2024-05-21_)
- :dart: feat: add polars and fsspec for testing getting data with dataset. (_2024-05-21_)
- :dart: feat: add minio docker compose file for testing load and push data to s3. (_2024-05-21_)
- :dart: feat: update sftp vendor code. (_2024-05-21_)
- :dart: feat: add docker compose file for sftp server. (_2024-05-20_)
- :dart: feat: add ping for sqlite connection. (_2024-05-20_)
- :dart: feat: add dict utils that reference from metadict. (_2024-05-19_)
- :dart: feat: add simple stage for dynamic passing from pipeline catalog. (_2024-05-19_)
- :dart: feat: add execute method on pipeline. (_2024-05-19_)
- :dart: feat: add Pipeline for getting workflow statement. (_2024-05-18_)
- :dart: feat: add params passing on simple loading obj. (_2024-05-18_)
- :dart: feat: add regex conf for search value on caller. (_2024-05-18_)
- :dart: feat: migrate code from ddeutil-io to this project. (_2024-05-14_)

### :black_nib: Code Changes

- :test_tube: tests: remove params on pipeline test cases. (_2024-05-26_)
- :test_tube: tests: add print current path on tests workflow. (_2024-05-24_)
- :construction: refactored: move dict and schedule to vendors. (_2024-05-21_)
- :test_tube: tests: add testcase for connection and rename demo file. (_2024-05-19_)
- :test_tube: tests: add test case for schedule. (_2024-05-19_)
- :test_tube: tests: final fix for schedule test case. (_2024-05-19_)
- :test_tube: tests: add tz2str util func for change tz on schedule test case. (_2024-05-19_)
- :test_tube: tests: add dotenv settig before running pytest. (_2024-05-19_)
- :construction: refactored: move legacy code to it dir for remove in the future. (_2024-05-18_)
- :test_tube: tests: fix testcase on base schedule object. (_2024-05-18_)
- :test_tube: tests: change respec value from testcase. (_2024-05-18_)
- :construction: refactored: change package name from pipe to workflow. (_2024-05-18_)
- :art: style: add fix line-length on ruff. (_2024-05-17_)
- :construction: refactored: refactored code that compatable with ddeutil-io. (_2024-05-17_)
- :test_tube: tests: add mockup data for testing loader module. (_2024-05-16_)
- :test_tube: tests: add testcase for loader module. (_2024-05-16_)
- :construction: refactored: refactore input param on loader. (_2024-05-16_)
- :construction: refactored: refactored modules on this project. (_2024-05-15_)
- :construction: refactored: Initial commit (_2024-05-14_)

### :card_file_box: Documents

- :page_facing_up: docs: update readme docs for tasks and hooks example. (_2024-05-26_)
- :page_facing_up: docs: update docs on readme. (_2024-05-22_)
- :page_facing_up: docs: update docs for running container on local. (_2024-05-21_)
- :page_facing_up: docs: update docs for noting in installation. (_2024-05-19_)
- :page_facing_up: docs: change proj name from pipe to worflow. (_2024-05-19_)
- :page_facing_up: docs: update readme file support yaml syntax change. (_2024-05-16_)

### :bug: Fix Bugs

- :gear: fixed: fix path of mount volumn on docker compose file. (_2024-05-24_)
- :gear: fixed: fix prepare slash func on connection obj. (_2024-05-24_)
- :gear: fixed: fix conn obj does not get endpoint from dataset loader. (_2024-05-24_)
- :gear: fixed: add options conversion for save and load polars datafrmae. (_2024-05-23_)
- :gear: fixed: remove seperate syntax on shell stage. (_2024-05-22_)
- :gear: fixed: add tzinfo assert to schedule test case. (_2024-05-19_)
- :gear: fixed: cronjob obj does not use tz info when passing together with start_date. (_2024-05-19_)
- :gear: fixed: add __about__ file for install with -e option. (_2024-05-19_)

### :package: Build & Workflow

- :toolbox: build: update deps on tests workflow. (_2024-05-24_)
- :toolbox: build: reformat test workflow. (_2024-05-24_)
- :toolbox: build: add test deps for install when workflow was run. (_2024-05-21_)
- :toolbox: build: rename package from pipe to workflow on pyproject. (_2024-05-19_)
- :toolbox: build: update ddeutil for test workflow. (_2024-05-19_)
- :toolbox: build: remove black from pre-commit step. (_2024-05-16_)

### :postbox: Dependencies

- :pushpin: deps: update dependency of polars. (_2024-05-24_)
- :pushpin: deps: remove dateutils from proj. (_2024-05-19_)
