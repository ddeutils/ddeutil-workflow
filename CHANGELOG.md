# Changelogs

## Latest Changes

## 0.0.3

### :sparkles: Features

- :dart: feat: add prepare params before passing to pipeline. (_2024-06-09_)
- :dart: feat: change some model obj from pydantic to msgspec. (_2024-06-09_)
- :dart: feat: add queue for handle needs job if before that do not run. (_2024-06-09_)
- :dart: feat: add exclude and include logic to matrix feat. (_2024-06-08_)
- :dart: feat: add matrix value on job model. (_2024-06-07_)
- :dart: feat: rename scdl to schedule. (_2024-06-06_)

### :black_nib: Code Changes

- :construction: refactored: move connection and dataset to vendors. (_2024-06-09_)
- :construction: refactored: change noted docs and prepare params output. (_2024-06-08_)
- :art: style: change print statement to logging and add pytest conf. (_2024-06-08_)

### :card_file_box: Documents

- :page_facing_up: docs: update docs-string on pipeline model objs. (_2024-06-10_)
- :page_facing_up: docs: add noted docs on needs job process. (_2024-06-09_)
- :page_facing_up: docs: add try-except for checking polars deps. (_2024-06-08_)

### :bug: Fix Bugs

- :gear: fixed: remove Params from ddeutil-io and use own params instead. (_2024-06-09_)
- :gear: fixed: revert moving connection to vendors. (_2024-06-09_)
- :gear: fixed: remove legacy dir on pyproject. (_2024-06-06_)

## 0.0.2

### :sparkles: Features

- :dart: feat: add from_dict cls method to connection. (_2024-05-30_)
- :dart: feat: add spark docker compose for test pyspark dataframew. (_2024-05-29_)
- :dart: feat: add scan for getting lazy frame on polars tasks. (_2024-05-28_)
- :dart: feat: add Params model on pipeline for validate context. (_2024-05-27_)
- :dart: feat: change name of map_caller to map_params. (_2024-05-27_)
- :dart: feat: remove manual registry and use tag decorator function instead. (_2024-05-27_)

### :black_nib: Code Changes

- :construction: refactored: 📦 bump polars from 0.20.26 to 0.20.31 (_2024-06-03_)
- :construction: refactored: 📦 bump boto3 from 1.34.109 to 1.34.117 (_2024-06-01_)
- :construction: refactored: change key name and some values on example yml file. (_2024-05-30_)
- :construction: refactored: clear unuse function from loader from register. (_2024-05-28_)
- :construction: refactored: change type hint and add BaseStage model. (_2024-05-27_)

### :postbox: Dependencies

- :pushpin: deps: update ddeutil-io package version that merge models. (_2024-06-03_)

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
