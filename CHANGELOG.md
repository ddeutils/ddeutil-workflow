# Changelogs

## Latest Changes

## 0.0.15

### :sparkles: Features

- :dart: feat: remove deep copy context on workflow execution. (_2024-09-30_)
- :dart: feat: add caller dataclass for keep result from regex. (_2024-09-30_)

### :black_nib: Code Changes

- :test_tube: tests: change test file name from pipeline to workflow. (_2024-09-30_)

## 0.0.14

### :sparkles: Features

- :dart: feat: change regex of caller to new version that catch prefix and last. (_2024-09-30_)
- :dart: feat: move log filename to class var instead hard code. (_2024-09-30_)
- :dart: feat: change result class from pydantic basemodel to dataclass instead. (_2024-09-29_)
- :dart: feat: add start and end time on the result object. (_2024-09-29_)
- :dart: feat: change name by add suffic Data that use dataclass. (_2024-09-28_)

### :black_nib: Code Changes

- :test_tube: tests: add testcae workflow running with parallel. (_2024-09-29_)
- :art: styled: change code format. (_2024-09-29_)
- :test_tube: tests: add mock Config object for override env var. (_2024-09-28_)
- :art: styled: change position of utils function that create inside main module. (_2024-09-20_)
- :test_tube: tests: add override env func and add error key on stage result context. (_2024-09-20_)

### :card_file_box: Documents

- :page_facing_up: docs: remove comment for run multiprocess on the job exec. (_2024-09-29_)
- :page_facing_up: docs: update docs-string on the stage module. (_2024-09-28_)
- :page_facing_up: docs: update docs-str on schedule module. (_2024-09-28_)
- :page_facing_up: docs: update features content and readme. (_2024-09-20_)
- :page_facing_up: docs: add compare with state machine language site. (_2024-09-18_)
- :page_facing_up: docs: add mkdocs features. (_2024-09-18_)

### :bug: Fix Bugs

- :gear: fixed: change import workflow object on api module (_2024-09-29_)

### :package: Build & Workflow

- :toolbox: build: add python setup id on test and build. (_2024-09-18_)
- :toolbox: build: add docs workflow for create mkdocs page. (_2024-09-18_)

### :postbox: Dependencies

- :pushpin: deps: update fastapi version to 0.115.0. (_2024-09-20_)

## 0.0.13

### :sparkles: Features

- :dart: feat: add default value for getting the on from workflow schedule model. (_2024-09-13_)

### :black_nib: Code Changes

- :construction: refactored: 📦 update fastapi requirement from <1.0.0,==0.112.2 to ==0.114.1 (_2024-09-12_)
- :test_tube: tests: add testcase for incease coverage report. (_2024-09-03_)
- :construction: refactored: ⬆ bump pypa/gh-action-pypi-publish from 1.9.0 to 1.10.0 (_2024-09-01_)

### :card_file_box: Documents

- :page_facing_up: docs: update readme file for refs tools. (_2024-09-16_)
- :page_facing_up: docs: add emoji on readme. (_2024-09-13_)
- :page_facing_up: docs: update readme file for more detail of schedule. (_2024-09-13_)
- :page_facing_up: docs: update doc-string on stage and job modules. (_2024-09-13_)
- :page_facing_up: docs: update readme file for add more usage. (_2024-09-12_)
- :page_facing_up: docs: rename workflow name on example file and readme. (_2024-09-02_)
- :page_facing_up: docs: update pypi version on readme. (_2024-09-02_)

### :bug: Fix Bugs

- :gear: fixed: remove test locals and globals. (_2024-09-13_)
- :gear: fixed: update deps version of ddeutil-io. (_2024-09-13_)
- :gear: fixed: merge branch for receive update from remote. (_2024-09-03_)

### :package: Build & Workflow

- :toolbox: build: add build ci for test building docker image. (_2024-09-13_)
- :toolbox: build: fixed caching python deps on tests workflow. (_2024-09-13_)

### :postbox: Dependencies

- :pushpin: deps: update testing for support python version 3.13. (_2024-09-13_)
- :pushpin: deps: adjust fastapi version that able to use on api. (_2024-09-12_)

## 0.0.12

> [!NOTE]
> Change package name on PyPI from `ddeutil-pipe` to `ddeutil-workflow`.

### :bug: Fix Bugs

- :gear: fixed: change pypi package name from pipe to workflow. (_2024-09-01_)

## 0.0.11

### :sparkles: Features

- :dart: feat: add workflow api that able to run pipeline manaully. (_2024-08-27_)
- :dart: feat: add crud for schedule route on api component. (_2024-08-27_)
- :dart: feat: change on start up event of lifespan context. (_2024-08-27_)
- :dart: feat: add schedule routing path for manage schedule listener. (_2024-08-27_)

### :black_nib: Code Changes

- :construction: refactored: change Pipeline object to Workflow for miss-understanding to use. (_2024-09-01_)
- :art: styled: move Pipeline from pipeline to scheduler and job. (_2024-09-01_)

### :card_file_box: Documents

- :page_facing_up: docs: update refactored pipline object on docs. (_2024-09-01_)
- :page_facing_up: docs: update readme for host of api component. (_2024-08-31_)
- :page_facing_up: docs: update readme docs for support merging schedul package to main deps. (_2024-08-27_)

### :bug: Fix Bugs

- :gear: fixed: change registry module to get type on env. (_2024-08-31_)

### :postbox: Dependencies

- :pushpin: deps: remove standard from fastapi deps. (_2024-08-31_)
- :pushpin: deps: merge schedule option to main deps. (_2024-08-27_)

## 0.0.10

### :sparkles: Features

- :dart: feat: update cron feature that has many wildcard char. (_2024-08-26_)
- :dart: feat: support cronjob with year layer. (_2024-08-26_)
- :dart: feat: add serialize fields for workflow route. (_2024-08-26_)
- :dart: feat: add serialize on cronjob field for api. (_2024-08-26_)
- :dart: feat: add logging with package name on utils. (_2024-08-26_)
- :dart: feat: add logging with this package name for disable. (_2024-08-25_)
- :dart: feat: add excluded args on save log method. (_2024-08-25_)
- :dart: feat: update cli command. (_2024-08-25_)
- :dart: feat: add schedule model for support scheduler feature. (_2024-08-23_)
- :dart: feat: change logic of pipeline release method. (_2024-08-23_)

### :black_nib: Code Changes

- :art: style: change code on repeat to func program. (_2024-08-26_)
- :art: style: change coding style for job and pipeline. (_2024-08-23_)
- :construction: refactored: change executer method name. (_2024-08-23_)
- :construction: refactored: move loader module to utils. (_2024-08-23_)

### :card_file_box: Documents

- :page_facing_up: docs: move getting started topic on readme to api docs. (_2024-08-26_)

### :bug: Fix Bugs

- :gear: fixed: remove default queue on release method that change iden of queue. (_2024-08-26_)
- :gear: fixed: move saving log on pipeline release step. (_2024-08-25_)
- :gear: fixed: merge branch 'main'. (_2024-08-24_)
- :gear: fixed: fix path of load_env for support cli. (_2024-08-23_)
- :gear: fixed: use logging instead override get logging func. (_2024-08-23_)

### :package: Build & Workflow

- :toolbox: build: change install pakcage with schedule. (_2024-08-23_)
- :toolbox: build: change install pakcage with schedule. (_2024-08-23_)

### :postbox: Dependencies

- :pushpin: deps: update typer to 0.12.5 and fastapi to 0.112.2. (_2024-08-26_)
- :pushpin: deps: remove fmtutil package deps from this project. (_2024-08-23_)

## 0.0.9

### :sparkles: Features

- :dart: feat: add optional raise error on stage object when env was set. (_2024-08-23_)
- :dart: feat: change logging directory pattern of log file model object. (_2024-08-22_)
- :dart: feat: add log saving on schedule features. (_2024-08-22_)
- :dart: feat: add cli and script endpoint of this project. (_2024-08-21_)
- :dart: feat: add api without using apscheduler. (_2024-08-21_)
- :dart: feat: add get latest log from log object. (_2024-08-21_)
- :dart: feat: update code for app that use schedule. (_2024-08-19_)
- :dart: feat: add priority queue on release pipline method. (_2024-08-18_)
- :dart: feat: change job parallel from process to thread. (_2024-08-18_)
- :dart: feat: add file log to pipeline release. (_2024-08-17_)
- :dart: feat: add params template for poke method that use. elease. prefix (_2024-08-17_)
- :dart: feat: add validate stage id and name should not template rather than matrix. (_2024-08-16_)

### :black_nib: Code Changes

- :test_tube: tests: change testcase that not use running id for check eq. (_2024-08-18_)
- :test_tube: tests: add more testcase for raise error result. (_2024-08-16_)
- :art: style: add type hint on stage object. (_2024-08-16_)

### :card_file_box: Documents

- :page_facing_up: docs: update readme for adding this workflow project rule to use. (_2024-08-19_)
- :page_facing_up: docs: update readme file and doc-string. (_2024-08-17_)
- :page_facing_up: docs: update readme and change usage example. (_2024-08-17_)
- :page_facing_up: docs: update readme and main propose of this project. (_2024-08-17_)
- :page_facing_up: docs: remove usage topic on readme. (_2024-08-16_)

### :bug: Fix Bugs

- :gear: fixed: update env var on testcase. (_2024-08-23_)
- :gear: fixed: change assert does not valid on log testcase. (_2024-08-21_)
- :gear: fixed: change logic of release with priority queue. (_2024-08-19_)
- :gear: fixed: change receive result on result object. (_2024-08-18_)
- :gear: fixed: fix import rich does not found. (_2024-08-17_)
- :gear: fixed: change way to receive running executor ID from pipeline on job and stage obj. (_2024-08-17_)

### :package: Build & Workflow

- :toolbox: build: remove list deps stage on tests workflow. (_2024-08-21_)

## 0.0.8

### :sparkles: Features

- :dart: feat: add running id for job and pipeline objects. (_2024-08-16_)
- :dart: feat: add decorator function for error handler on stage object. (_2024-08-16_)
- :dart: feat: improve exception error should not raise from execution. (_2024-08-15_)
- :dart: feat: add filter function on job strategy execution. (_2024-08-15_)

### :black_nib: Code Changes

- :test_tube: tests: add pipeline poke testcase. (_2024-08-15_)
- :construction: refactored: split the large execute function on job and pipeline to private funcs. (_2024-08-15_)

### :card_file_box: Documents

- :page_facing_up: docs: update readme and move hook stage example to docs/. (_2024-08-16_)
- :page_facing_up: docs: update readme on installation topic. (_2024-08-15_)

### :bug: Fix Bugs

- :gear: fixed: change logging of catch methods on job object. (_2024-08-16_)

## 0.0.7

### :sparkles: Features

- :dart: feat: add remove prefix map in hook stage support special param name. (_2024-08-15_)
- :dart: feat: pipeline execute can run parallel job that not need deps. (_2024-08-15_)
- :dart: feat: add job_execute method on pipeline object. (_2024-08-15_)
- :dart: feat: implement fail-fast for job strategy executor. (_2024-08-15_)
- :dart: feat: add muti-processing when job startegy make more than one. (_2024-08-14_)
- :dart: feat: add strategy execution for support parallel job execution. (_2024-08-14_)
- :dart: feat: add fastapi app for handler pipeline schedule. (_2024-08-14_)
- :dart: feat: add poke and release methods on pipeline object. (_2024-08-13_)
- :dart: feat: add search env to param2template utils function. (_2024-08-13_)
- :dart: feat: implement passing arguments to custom filter function. (_2024-08-13_)
- :dart: feat: add post-filter on regex caller that extract from template value. (_2024-08-13_)
- :dart: feat: add post-filter value on caller regex. (_2024-08-13_)
- :dart: feat: change exception on utils to sub-exception class of workflow class. (_2024-08-12_)

### :black_nib: Code Changes

- :test_tube: tests: config python logging and coverage omit files. (_2024-08-13_)

### :card_file_box: Documents

- :page_facing_up: docs: init and update example docs. (_2024-08-12_)
- :page_facing_up: docs: update config value of this package on readme. (_2024-08-12_)
- :page_facing_up: docs: update readme for add hook function example. (_2024-08-12_)

## 0.0.6

### :sparkles: Features

- :dart: feat: change output of any execution from dict to result dataclass. (_2024-08-12_)
- :dart: feat: add default stage id that was generated from stage name. (_2024-08-12_)
- :dart: feat: add result context for job execution process. (_2024-08-12_)
- :dart: feat: add finditer on the param2template util func support multi replace. (_2024-08-11_)
- :dart: feat: add set output method calling step to job execution process. (_2024-08-11_)
- :dart: feat: add result context to each execution dependency. (_2024-08-11_)
- :dart: feat: add is_skip method on stage and parameterize on pipeline. (_2024-08-10_)
- :dart: feat: add template class variable for dynamic templating params. (_2024-08-09_)
- :dart: feat: add default empty job and change validate condition of strategy. (_2024-08-09_)
- :dart: feat: add dash2underscore on utils func. (_2024-08-09_)
- :dart: feat: add trigger stage to pipeline model. (_2024-08-09_)
- :dart: feat: add ignore content for diagram backup file. (_2024-08-08_)
- :dart: feat: add on in pipeline model. (_2024-08-07_)
- :dart: feat: add dynamic import registry object from list of module path. (_2024-08-07_)
- :dart: feat: remove workflow config file and use env var instend. (_2024-08-07_)

### :black_nib: Code Changes

- :construction: refactored: change shell stage to bash stage. (_2024-08-10_)
- :construction: refactored: change task stage to hook stage. (_2024-08-10_)
- :test_tube: tests: change name of config name that use for test. (_2024-08-09_)
- :construction: refactored: deprecate make_strategy method from job to strategy model. (_2024-08-09_)
- :art: style: change code format on the on model. (_2024-08-09_)
- :construction: refactored: move validate on key in pipeline to classmethod. (_2024-08-08_)
- :test_tube: tests: add testcase for pipeine on and desc. (_2024-08-07_)
- :construction: refactored: change schedule object name to On and merge code regex file. (_2024-08-07_)
- :test_tube: tests: uncomment schedule testcase. (_2024-08-06_)

### :card_file_box: Documents

- :page_facing_up: docs: update readme for installation with app. (_2024-08-11_)
- :page_facing_up: docs: update readme for deployment topic. (_2024-08-10_)
- :page_facing_up: docs: delete backup diagram file that already add to repo. (_2024-08-08_)
- :page_facing_up: docs: update readme for config content and remove license. (_2024-08-07_)
- :page_facing_up: docs: update readme file for deprecated feature. (_2024-08-07_)

### :bug: Fix Bugs

- :gear: fixed: revert change timezone on github action. (_2024-08-08_)
- :gear: fixed: change logic of timezone value that pass to cron runner. (_2024-08-08_)
- :gear: fixed: fix cronjob validate does not valid. (_2024-08-08_)
- :gear: fixed: move conf path on testcase. (_2024-08-07_)

### :package: Build & Workflow

- :toolbox: build: remove change timezone on tests action. (_2024-08-08_)

### :postbox: Dependencies

- :pushpin: deps: remove schedule package from this project. (_2024-08-07_)

## 0.0.5

### :sparkles: Features

- :dart: feat: add unit dataclass on scheduler. (_2024-06-15_)
- :dart: feat: add on and desc fields on pipeline model. (_2024-06-12_)
- :dart: feat: add env variables for shell stage executor. (_2024-06-11_)

### :black_nib: Code Changes

- :test_tube: tests: update testcase that was remove polars package. (_2024-08-06_)
- :construction: refactored: 📦 bump pyarrow from 16.1.0 to 17.0.0 (_2024-08-01_)
- :construction: refactored: 📦 bump boto3 from 1.34.136 to 1.34.151 (_2024-08-01_)
- :construction: refactored: ⬆ bump pypa/gh-action-pypi-publish from 1.8.14 to 1.9.0 (_2024-07-01_)
- :construction: refactored: 📦 bump boto3 from 1.34.117 to 1.34.136 (_2024-07-01_)
- :construction: refactored: 📦 bump fsspec from 2024.5.0 to 2024.6.1 (_2024-07-01_)
- :construction: refactored: 📦 bump sqlalchemy from 2.0.30 to 2.0.31 (_2024-07-01_)
- :construction: refactored: __schedule module to scheduler. (_2024-06-14_)
- :construction: refactored: merge run example conf file together. (_2024-06-11_)

### :card_file_box: Documents

- :page_facing_up: docs: update docs string on workflow objects. (_2024-08-06_)
- :page_facing_up: docs: update readme for little detail. (_2024-07-29_)
- :page_facing_up: docs: add license shield on readme. (_2024-06-15_)
- :page_facing_up: docs: add docs-string on loader add merge schedule object. (_2024-06-13_)

### :bug: Fix Bugs

- :gear: fixed: remove all vendors to ddeutil-vendors project. (_2024-08-06_)
- :gear: fixed: fix generate crontab value use dow when interval is monthly. (_2024-06-12_)

### :postbox: Dependencies

- :pushpin: deps: add schedule deps and rename schedule to on. (_2024-06-12_)

## 0.0.4

### :sparkles: Features

- :dart: feat: add executable function for shell file. (_2024-06-11_)
- :dart: feat: add prepare shell script on the shell stage. (_2024-06-10_)

### :black_nib: Code Changes

- :test_tube: tests: add logging on test-case. (_2024-06-10_)
- :test_tube: tests: add test-case for shell script execution. (_2024-06-10_)

### :bug: Fix Bugs

- :gear: fixed: change shell flag on subprocess for shell stage. (_2024-06-11_)
- :gear: fixed: add debug logging for test shell stage executor. (_2024-06-11_)
- :gear: fixed: remove shabang and dynamic cmd. (_2024-06-11_)
- :gear: fixed: shell stage does not return the same result. (_2024-06-10_)

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
