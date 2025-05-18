# Changelogs

## Latest Changes

## 0.0.66

### :sparkles: Features

- :dart: feat: add cli module.
- :dart: feat: remove raise when job skip on the jon exec.
- :dart: feat: add excluded parameter on release method.

### :bug: Bug fixes

- :gear: fixed: remove caller secret import.

### :black_nib: Code Changes

- :test_tube: tests: add validate release testcase.

### :package: Build & Workflow

- :toolbox: build: prepare config on the pyproject file.

### :book: Documentations

- :page_facing_up: docs: update docs-string.

## 0.0.65

### :sparkles: Features

- :dart: feat: add workflow raise error on job exec.
- :dart: feat: remove result param from workflow exec.
- :dart: feat: add return status from workflow job exec method.
- :dart: feat: revise context and params for more performance and monitoring improvements (#47)
- :dart: feat: draft caller exception for call stage.

### :bug: Bug fixes

- :gear: fixed: change config on parallel stage.

### :black_nib: Code Changes

- :test_tube: tests: add testcase support foreach stage exec concurrent.
- :art: format: clean and revise job exec on workflow model.
- :test_tube: tests: update testcase for job exec method on workflow model.
- :construction: refactored: change exception to error for minimal styled.
- :test_tube: tests: update testcase for making coverage.

### :broom: Deprecate & Clean

- :recycle: clean: remove workflow poke and task object.

## 0.0.64

### :stars: Highlight Features

- :star: hl: change validation of caller function args to dynamic model validation.
- :star: hl: support type adapter on caller function argument.

### :bug: Bug fixes

- :gear: fixed: remove not use args on model dump.

### :black_nib: Code Changes

- :test_tube: tests: fix invalid testcase.
- :construction: refactored: remove schedule module.

### :broom: Deprecate & Clean

- :recycle: clean: remove schedule route marking.

### :book: Documentations

- :page_facing_up: docs: remove scheduler docs.

## 0.0.63

### :stars: Highlight Features

- :star: hl: create WorkflowSecret for pass env var before get secret value and binding when export to json.

### :sparkles: Features

- :dart: feat: add pass_env before start stage execution (#44)
- :dart: feat: draft create model from caller func.
- :dart: feat: draft mark secret value on result context.

### :black_nib: Code Changes

- :test_tube: tests: add testcase for draft create model for function args.

### :postbox: Dependencies

- :pushpin: deps: add pydantic-extra-types for extra timezone type validation.

### :book: Documentations

- :page_facing_up: docs: update docs-string.
- :page_facing_up: docs: update readme file.

## 0.0.62

### :sparkles: Features

- :dart: feat: add mark argument on templating and template filtering functions.
- :dart: feat: add more filter build-in functions.

### :black_nib: Code Changes

- :test_tube: tests: update testcase of __cron.
- :test_tube: tests: fixed testcase that not valid with feature changed.
- :art: format: change typed-hint on __cron module.

## 0.0.61

### :stars: Highlight Features

- :star: hl: add traceback logging on trace log when stage got raise error.

### :sparkles: Features

- :dart: feat: add keys and values template filter for extract dict value.
- :dart: feat: add dump_all model result recursive on caller stage result.

### :black_nib: Code Changes

- :art: format: add typed-hint on params module.
- :construction: refactored: seperate queue and poke methods from workflow model to workflow poke model.
- :test_tube: tests: update pyvirtual stage testcase.
- :art: format: move prepare message log to `make_message` method.

## 0.0.60

### :sparkles: Features

- :dart: feat: add emoji to trace log with log prefix.
- :dart: feat: add extract message prefix log.

### :bug: Bug fixes

- :gear: fixed: testcase from feature change does not valid.
- :gear: fixed: running id that use on trigger stage not valid.
- :gear: fixed: pass run id to trigger stage exec for merge trace log together.
- :gear: fixed: move current frame from dynamic method to make method.

### :black_nib: Code Changes

- :test_tube: tests: add testcase for create full example workflow usecase.
- :test_tube: tests: update traces testcase.
- :test_tube: tests: fixed testcase and change typed-hint on utils mod.

### :postbox: Dependencies

- :pushpin: deps: update deps for self-hosted job.

### :book: Documentations

- :page_facing_up: docs: update docs-string and field desc.

## 0.0.59

### :sparkles: Features

- :dart: feat: add log level on the trace data.

### :bug: Bug fixes

- :gear: fixed: init audit log model pass position arg.
- :gear: fixed: add deepcopy on value and extend or append.

### :black_nib: Code Changes

- :test_tube: tests: revise example testcase for parallel stage.
- :art: format: change type annotation for py39.

### :package: Build & Workflow

- :toolbox: build: revert add uv install on tests workflow.
- :toolbox: build: update pre-commit hook to v5.0.0.
- :package: build: bump pydantic from 2.11.1 to 2.11.4 (#38)

### :postbox: Dependencies

- :pushpin: deps: add uvicorn package on all tag.
- :pushpin: deps: update ddeutil-io to 0.2.13.

## 0.0.58

### :sparkles: Features

- :dart: feat: revise tests gh workflow (#37)
- :dart: feat: add use_index_as_key support foreach on duplicate key.

### :bug: Bug fixes

- :gear: fixed: add debug on uv venv step.
- :gear: fixed: always install pytest.
- :gear: fixed: uv run pytest not spawn module.
- :gear: fixed: remove python version 3.13t from tests action.

### :black_nib: Code Changes

- :lipstick: styled: draft emoji for logging prefix.
- :test_tube: tests: split complex stage testcase to example.

### :package: Build & Workflow

- :toolbox: build: reformat test workflow.
- :toolbox: build: update test with uv.

## 0.0.57

### :stars: Highlight Features

- :star: hl: revise error context from multi-parallel execution.
- :star: hl: add tz validate if pass different timezone in the same workflow.
- :star: hl: remove class key on errors context.

### :sparkles: Features

- :dart: feat: add cancel error handler error on job exec.
- :dart: feat: update async function on the bash stage.
- :dart: feat: change code not handler error on workflow exec method.
- :dart: feat: add remove queue in running on mark complete method.
- :dart: feat: revise poking and release method.

### :bug: Bug fixes

- :gear: fixed: testcase that run base on cpu bound.
- :gear: fixed: remove util exception class that not raise from stage exec.

### :black_nib: Code Changes

- :test_tube: tests: update testcase for make coverage.
- :art: format: change log stetement.
- :test_tube: tests: create testcase for make coverage.
- :test_tube: tests: fix test case that change error statement.
- :test_tube: tests: add testcase for cron runner object.
- :art: format: revise poking method.
- :test_tube: tests: add testcase for change datetime with timezone.
- :test_tube: tests: update poking function on workflow module.
- :lipstick: styled: change trace log message style.
- :construction: format: change code format on poke method.
- :test_tube: tests: add testcase for raise stage exec.
- :art: styled: improve logging statement of stages module.

### :broom: Deprecate & Clean

- :recycle: clean: remove unuse field on release object.

### :package: Build & Workflow

- :toolbox: build: update clishelf version from 0.2.19 to 0.2.22.

### :postbox: Dependencies

- :pushpin: deps: update ddeutil package base version.

### :book: Documentations

- :page_facing_up: docs: update context docs.
- :page_facing_up: docs: update readme file for warning scheduler feature.

## 0.0.56

### :stars: Highlight Features

- :star: hl: support multiple config path on fileload object.

### :bug: Bug fixes

- :gear: fixed: add type check on model validate before mode.

### :black_nib: Code Changes

- :test_tube: tests: revise some testcase that not use.
- :test_tube: tests: update event testcase.
- :test_tube: tests: update get tz key on from_value construct func.
- :test_tube: tests: fixed testcase for removing from_path classmethod.
- :art: styled: change cron module to event.
- :test_tube: tests: improve stage exec testcase.

### :broom: Deprecate & Clean

- :recycle: clean: remove simload object and use fileload instead.
- :recycle: clean: remove from_path on workflow model.

## 0.0.55

### :sparkles: Features

- :dart: feat: update api code and restructure api component.

### :broom: Deprecate & Clean

- :recycle: clean: remove useless method on workflow module.

## 0.0.54

### :stars: Highlight Features

- :star: hl: remove raise error on job execution.
- :star: hl: merge seperate threading method on workflow model.

### :sparkles: Features

- :dart: feat: add pass context before raise stage error on foreach stage.
- :dart: feat: draft convert step of bash stage to async mode.
- :dart: feat: draft docker stage task exec func.
- :dart: feat: draft python virtual stage.

### :black_nib: Code Changes

- :test_tube: tests: update expect value that differenct.
- :test_tube: tests: update testcase for change raise message.
- :art: styled: change code format on job module.

### :postbox: Dependencies

- :pushpin: deps: remove hook stage.

## 0.0.53

### :stars: Highlight Features

- :star: hl: upgrade case-stage handle multiple stages.

### :black_nib: Code Changes

- :test_tube: tests: fix testcase that not valid.
- :test_tube: tests: update testcase for getting stage outputs inside foreach.

## 0.0.52

### :sparkles: Features

- :dart: feat: draft dynamic loader object on from_conf construction.

### :bug: Bug fixes

- :gear: fixed: remove use enum value config on job model.
- :gear: fixed: revise foreach stage does not pass stages variable from outside.
- :gear: fixed: enum type does not validate by default on job module.

### :black_nib: Code Changes

- :test_tube: tests: update testcase foreach stage that use multiple time.

## 0.0.51

### :sparkles: Features

- :dart: feat: add error handler on trigger stage model.
- :dart: feat: update code to catch error on non-threading exec.
- :dart: feat: draft float params.
- :dart: feat: add decimal parameter.
- :dart: feat: add default tag name to latest.
- :dart: feat: revise job set outputs method.
- :dart: feat: draft runs-on docker mode.
- :dart: feat: add skip-not-match args for skip if it does not match any case.
- :dart: feat: update draft for docker stage.
- :dart: feat: add extras to gen running id func on stages module.
- :dart: feat: revise parallel stage execution method.

### :bug: Bug fixes

- :gear: fixed: change expect result on job exec testcase.
- :gear: fixed: dynamic does not get funcitonal config if it convert boolean to False.
- :gear: fixed: empty ouput for setting job exec result.
- :gear: fixed: pass event to exec item on stages module.

### :black_nib: Code Changes

- :art: styled: format code on core module.
- :test_tube: tests: update testcase for job needs.
- :test_tube: tests: add testcase for make coverage.
- :art: styled: add docs-string and reformat code.

### :broom: Deprecate & Clean

- :recycle: clean: remove runs-on k8s type.
- :recycle: clean: revise workflow and logs code.

### :postbox: Dependencies

- :pushpin: deps: update ddeutil-io from 0.2.10 to 0.2.11.
- :pushpin: deps: update ddeutil from 0.4.6 to 0.4.7.

## 0.0.50

### :sparkles: Features

- :dart: feat: add cancel status.
- :dart: feat: revise until stage execution.
- :dart: feat: add result handle update nested key in context data.
- :dart: feat: add error handler on trigger stage.
- :dart: feat: add raise stage error when trigger stage return failed status.
- :dart: feat: revise cut running id func.
- :dart: feat: draft az batch job exec.
- :dart: feat: draft docker stage execution task.

### :black_nib: Code Changes

- :test_tube: tests: remove testcase that does not use.
- :test_tube: tests: add testcase for utils module.
- :construction: refactored: change rule and runs-on model.

### :broom: Deprecate & Clean

- :recycle: clean: remove job raise error config.
- :recycle: clean: remove raise_error from job exec on workflow module.

## 0.0.49

### :stars: Highlight Features

- :star: hl: add support for case match stage.
- :star: hl: add support for until stage.
- :star: hl: add support concurrent on the foreach stage.

### :sparkles: Features

- :dart: feat: split execution on the foreach stage.
- :dart: feat: add bypass extras argument to workflow task object.
- :dart: feat: add dynamic config on scheduler module.

### :bug: Bug fixes

- :gear: fixed: remove default on virtual python stage for make differ union.
- :gear: fixed: change config property name that not match with env key.
- :gear: fixed: remove extras that force pass on scheduler method.
- :gear: fixed: remove validate info for after mode model validation.

### :black_nib: Code Changes

- :test_tube: tests: fixed assert not valid with respec value.
- :construction: refactored: change logs object type and abstract method.

### :broom: Deprecate & Clean

- :recycle: clean: remove set default id config.
- :recycle: clean: remove root path on the config object.

## 0.0.48

### :sparkles: Features

- :dart: feat: add extras bypass to audit and trace objects on workflow module.
- :dart: feat: add extras argument passing to Release object.
- :dart: feat: add extras field on trace dataclass object.

### :bug: Bug fixes

- :gear: fixed: change import of get logger func.

### :black_nib: Code Changes

- :test_tube: tests: make coverage report.
- :construction: refactored: move get_logger to logs module instead of conf.

## 0.0.47

### :stars: Highlight Features

- :star: hl: add parsing pydantic model on the call stage.

### :sparkles: Features

- :dart: feat: support add result dataclass instance to kwargs parameter.

### :bug: Bug fixes

- :gear: fixed: remove debug code.

### :broom: Deprecate & Clean

- :recycle: clean: clean the result module.

### :package: Build & Workflow

- :toolbox: build: remove production metadata that not push to testpypi.

## 0.0.46

### :sparkles: Features

- :dart: feat: add main file for future cli implementation.

### :bug: Bug fixes

- :gear: fixed: add override extras on workflow and job exections.

### :broom: Deprecate & Clean

- :recycle: clean: remove base config object.

### :package: Build & Workflow

- :toolbox: build: change beta to production grade.

## 0.0.45

### :stars: Highlight Features

- :star: hl: implement conf_path override on loader object.

## 0.0.44

### :bug: Bug fixes

- :gear: fixed: add break job streategy exec method if stage was raised.

### :black_nib: Code Changes

- :art: styled: move async testcase to async folder.
- :construction: refactored: change non-threading exec to context pool instead.
- :test_tube: tests: fix testcase for stage not success.
- :test_tube: tests: fixed testcase on job strategy exec.
- :test_tube: tests: add testcase for testing job trigger check method return failed.

### :broom: Deprecate & Clean

- :recycle: clean: remove comment that not important.

## 0.0.43

### :stars: Highlight Features

- :star: hl: support for array and map param.

### :black_nib: Code Changes

- :test_tube: tests: update testcase that not valid.
- :test_tube: tests: add testcase for support trigger stage in foreach stage.
- :test_tube: tests: add workflow exec override conf by extras testcase.

### :broom: Deprecate & Clean

- :recycle: clean: change making error message to to_dict method.
- :recycle: clean: remove trigger state object and use status instead.

## 0.0.42

### :stars: Highlight Features

- :star: hl: change constuction from from_loader to from_conf.
- :star: hl: add dynamic config that can override with extras.
- :star: hl: add foreach support params template.

### :sparkles: Features

- :dart: feat: pass event from trigger stage to workflow execution.
- :dart: feat: draft async function on stage.
- :dart: feat: change config component for audit to log.
- :dart: feat: change fix config on workflow module to fully-dynamic.
- :dart: feat: add dynamic config and marking module that dynamic or not.
- :dart: feat: add bypass extras to param2template.

### :bug: Bug fixes

- :fire: hotfix: add check extras on dynamic conf func.
- :gear: fixed: rename registry config that change the name.

### :black_nib: Code Changes

- :test_tube: tests: add mark asyncio.
- :test_tube: tests: add max job parallel for raise workflow testcase.
- :test_tube: tests: update testcase for minor change of conf module.
- :test_tube: tests: add testcase for get extras passing from workflow.
- :art: styled: add docs-string and add no cov comment.

### :broom: Deprecate & Clean

- :recycle: clean: remove context module.
- :recycle: clean: remove not-important comment.
- :recycle: clean: remove config project scope.

### :package: Build & Workflow

- :toolbox: build: add pre-commit support test not schedule tag.

## 0.0.41

### :stars: Highlight Features

- :star: hl: add extras field on workflow, job, and stage model.
- :star: hl: add event to stage execution.

### :sparkles: Features

- :dart: feat: add awriter method on trace object support async.
- :dart: feat: update raise stage execution.
- :dart: feat: draft job execution on the self-hosted.
- :dart: feat: add filter empty file on simload object.
- :dart: feat: add registries on extract_call func.

### :bug: Bug fixes

- :gear: fixed: change test filename.
- :gear: fixed: change import caller that move to reusables.
- :gear: fixed: change import audits from api component.
- :gear: fixed: change audit import that cleaned.

### :black_nib: Code Changes

- :test_tube: tests: change import caller.

### :broom: Deprecate & Clean

- :recycle: clean: merge audit module to logs.
- :recycle: clean: merge caller and templates module.
- :recycle: clean: remove duplicate row on setting dotenv.

## 0.0.40

### :stars: Highlight Features

- :star: hl: add. rom_path construct on the Schedule model
- :star: hl: add. rom_path construct on the Workflow model

### :bug: Bug fixes

- :gear: fixed: revise filter ignore condition on simload object.

### :black_nib: Code Changes

- :construction: typo: add type-hint on __cron module.

### :package: Build & Workflow

- :package: build: bump pydantic from 2.10.6 to 2.11.1 (#34)
- :package: build: bump python-dotenv from 1.0.1 to 1.1.0 (#35)

### :postbox: Dependencies

- :pushpin: deps: update version ddeutil-io[yaml,toml] from 0.2.8 to 0.2.10.
- :pushpin: deps: update ddeutil-io from 0.2.3 to 0.2.8.

## 0.0.39

### :stars: Highlight Features

- :star: hl: add condition on job model by alias if value.
- :star: hl: add condition for check job trigger rules.

### :sparkles: Features

- :dart: feat: add support skip checking result from job trigger rule check.
- :dart: feat: add check condition on workflow exec method.
- :dart: feat: add return result on job exec if event was set.
- :dart: feat: add support ? template for check caller exist.

### :bug: Bug fixes

- :gear: fixed: update skipped field on context objects.
- :gear: fixed: commnet assert for workflow poking that not make sense.
- :gear: fixed: change default factory of update field from config tz.

### :black_nib: Code Changes

- :test_tube: tests: add job is_skipped testcase for make coverage.
- :test_tube: tests: fix failed testcase.

## 0.0.38

### :stars: Highlight Features

- :star: hl: support cancel stage from workflow execution timeout.
- :star: hl: add context module for keep context models.

### :sparkles: Features

- :dart: feat: change RunsOn model to annotated object.
- :dart: feat: add to argument on stage handle exec method.
- :dart: feat: add event on workflow execution for cancel if it timeout.
- :dart: feat: remove deep_copy func that was deleted.
- :dart: feat: add support async function on call stage.
- :dart: feat: add parallel and foreach stages. (#29)

### :bug: Bug fixes

- :gear: fixed: move locals contruct to globals on pystage.
- :gear: fixed: remove exception class name before error message.
- :gear: fixed: testcase that assert matrix key.
- :gear: fixed: rewrite checking condition for make sigle future thread pool.
- :gear: fixed: remove matrix key from none-strategy exec.
- :gear: fixed: change name of context model.
- :gear: fixed: fix return context from job exec route.
- :gear: fixed: remove logger from stages module.
- :gear: fixed: fix error statement for necessary params on call stage.

### :black_nib: Code Changes

- :test_tube: tests: add testing condition for schedule on py39 only.
- :test_tube: tests: fix workflow exec does not valid.
- :test_tube: tests: add testcase for context models on result module.
- :art: styled: not sync deps for future improvement.
- :art: styled: add query and path params.

### :broom: Deprecate & Clean

- :recycle: clean: add to_dict method on exception object.
- :recycle: clean: clean code on job module.
- :recycle: clean: remove function that does not use on utils module.

## 0.0.37

### :stars: Highlight Features

- :star: hl: add dynamic job runs-on execute func.

### :sparkles: Features

- :dart: feat: move execute strategy from method to func.
- :dart: feat: change logic of gen_id.

### :black_nib: Code Changes

- :test_tube: tests: add testcase for job execute with self-hosted.
- :test_tube: tests: update testcase for cover coverage.
- :art: styled: change log name of routes from workflow to uvicorn.
- :test_tube: tests: update testcase for workflows on api component.

### :package: Build & Workflow

- :toolbox: build: add uv dockerfile support uv building.

## 0.0.36

### :sparkles: Features

- :dart: feat: update job route on api component.
- :dart: feat: add date param model object.
- :dart: feat: add logs routes for audit log.
- :dart: feat: add TraceData on init file.
- :dart: feat: update logs route on api component.
- :dart: feat: add TraceData object for keep trace data context.
- :dart: feat: add jobs route for support self-hosted trigger.
- :dart: feat: mark next feature on stages module.

### :bug: Bug fixes

- :gear: fixed: change trace log parent id that not valid on scheduler module.
- :gear: fixed: link stage page does not valid.

### :black_nib: Code Changes

- :test_tube: tests: add testcase for job execution route.
- :test_tube: tests: update testcase for api.
- :test_tube: tests: exclude route files for coverage.

### :broom: Deprecate & Clean

- :recycle: clean: clear code on logs module.

### :package: Build & Workflow

- :toolbox: build: update .dockerignore file.

### :postbox: Dependencies

- :pushpin: deps: update ujson package on api deps.

## 0.0.35

### :stars: Highlight Features

- :star: hl: create RunOn model for support dynamic job executor.

### :sparkles: Features

- :dart: feat: move trace property to field of Result object.
- :dart: feat: move route module to dir instead.
- :dart: feat: add logs route.

### :black_nib: Code Changes

- :construction: clear: add type hint and clear method that not use.

### :broom: Deprecate & Clean

- :recycle: clean: split logs module from result module.

## 0.0.34

### :stars: Highlight Features

- :star: hl: add confignore support for filter config data.
- :star: hl: revise job execution logic for fail-fast and complete.
- :star: hl: change hook stage to call stage.
- :star: hl: add parent run id trace log.
- :star: hl: change catch error data from workflow execution.
- :star: hl: change catch error data from job execution.
- :star: hl: change catch error data from stage execution.

### :sparkles: Features

- :dart: feat: pass config to trace log object.
- :dart: feat: add return result from schedule_task function.
- :dart: feat: update optional arg on app file.
- :dart: feat: pass parent running id to workflow release from poke method.
- :dart: feat: change return type of poking from list[Result] to Result.
- :dart: feat: add filter class on python stage.
- :dart: feat: add deep_copy util func.

### :bug: Bug fixes

- :gear: fixed: remove format on string datetime.
- :gear: fixed: default path of audits and logic of shcedule pending.
- :gear: fixed: change TraceLog from object to dataclass.
- :gear: fixed: add traceback and adjust stacklevel for logging.
- :gear: fixed: rename method of audit object that use log prefix.
- :gear: fixed: fix testcase does not valid.

### :black_nib: Code Changes

- :test_tube: tests: fixed audit on testcase.
- :test_tube: tests: add result object on hook function.

## 0.0.33

### :stars: Highlight Features

- :star: hl: add execute_time field on the Audit model.
- :star: hl: split log objects from config module to logs module.

### :sparkles: Features

- :dart: feat: use result instead of run_id.
- :dart: feat: add result argument on job execution.
- :dart: feat: add trace log on workflow execution.
- :dart: feat: mark TraceLog object for logging.
- :dart: feat: mark TraceLog object for logging.
- :dart: feat: pass result to workflow exec instead of run_id.
- :dart: feat: update log config.

### :bug: Bug fixes

- :gear: fixed: move default running id function out of model validate.
- :gear: fixed: rename logs module to audit module.

### :black_nib: Code Changes

- :test_tube: tests: fixed testcase on conf module.
- :fast_forward: merge: branch 'main' of https://github.com/ddeutils/ddeutil-workflow.
- :test_tube: tests: fixed import invalid module.

### :broom: Deprecate & Clean

- :recycle: clean: remove un-use method on the result model.

## 0.0.32

### :stars: Highlight Features

- :star: hl: add pending method on the Schedule model.

### :bug: Bug fixes

- :gear: fixed: remove un-used attributes on app state.

### :black_nib: Code Changes

- :test_tube: tests: mark no coverage on TODO features.

## 0.0.31

### :sparkles: Features

- :dart: feat: typehint on scheduler module.
- :dart: feat: revise poke logic for checking current datetime.
- :dart: feat: add ReleaseType support the type field on Release object.
- :dart: feat: pass extras field to cronjob field with map to option arg.

### :bug: Bug fixes

- :gear: fixed: remove handler queue on the release method if it invalid type.

### :black_nib: Code Changes

- :art: styled: change typehint on catch schdule result.
- :test_tube: tests: mark schedule and change on tests workflow.
- :test_tube: tests: update testcase on the workflow poke module.
- :art: styled: refactore code and docs-string.
- :test_tube: tests: prepare testcase for the on model.
- :test_tube: tests: update testcase for release and release_queue object.
- :test_tube: tests: move test file from store on conf to conftest.

## 0.0.30

### :black_nib: Code Changes

- :construction: hi: change WorkflowQueue object name to ReleaseQueue instead.
- :construction: hi: change WorkflowRelease object name to Release instead.
- :test_tube: tests: update testcase for workflow exec hook.

### :package: Build & Workflow

- :toolbox: build: add issue template.

## 0.0.29

### :sparkles: Features

- :dart: feat: add ddeutil.vendors on registry search.

### :bug: Bug fixes

- :gear: fixed: change default of registry path.
- :gear: fixed: remove uv prefix.

### :black_nib: Code Changes

- :art: styled: add type hint on config module.
- :test_tube: tests: revert session arg.
- :art: styled: add typo on hook module.
- :test_tube: tests: add worker parallel on tests workflow.
- :test_tube: tests: add pytest_collection_modifyitems for more parallel action.
- :test_tube: tests: add markers for split testcase on gh action.
- :test_tube: tests: add more testcase and reformat code on tests.

### :package: Build & Workflow

- :toolbox: build: move puhlish workflow support oidc.
- :toolbox: build: mark parallel tests with pytest-xdist on tests workflow.
- :toolbox: build: adjust ignore file that use on build and tests gh workflow.

### :postbox: Dependencies

- :pushpin: deps: update deps for core package.

## 0.0.28

### :sparkles: Features

- :dart: feat: remove handler_result function in stage module and use handler_execution method instead.

### :bug: Bug fixes

- :gear: fixed: change config name of config path from `PATH_CONF` to `CONF_PATH`.
- :gear: fixed: remove upper route from api component.

### :black_nib: Code Changes

- :art: styled: re-format code on utils.
- :art: styled: change config pattern on readme page.
- :art: styled: typo the docs-string and comments.
- :package: refactored: bump pydantic from 2.10.5 to 2.10.6 (#27)
- :construction: refactored: ⬆ bump pypa/gh-action-pypi-publish from 1.12.3 to 1.12.4 (#26)
- :package: refactored: bump pydantic from 2.10.4 to 2.10.5

### :package: Build & Workflow

- :toolbox: build: add clishelf config.
- :toolbox: build: add sign python dist to gh release job.
- :toolbox: build: update prefix dependabot message.

### :postbox: Dependencies

- :pushpin: deps: update clishelf from 0.2.4 to 0.2.19.
- :pushpin: deps: update ddeutil==0.4.6.

## 0.0.27

### :sparkles: Features

- :dart: feat: adjust default value on registry config. (_2025-01-07_)

### :black_nib: Code Changes

- :test_tube: tests: add testcase for filter function. (_2025-01-07_)

### :bug: Fix Bugs

- :gear: fixed: revise log and config object. (_2025-01-07_)

## 0.0.26.post1

### :sparkles: Features

- :dart: feat: add code for sqlite logging. (_2025-01-07_)
- :dart: feat: add null handler for dev can propagate this logging. (_2025-01-07_)
- :dart: feat: change clas attrs on config object to property. (_2025-01-07_)

### :black_nib: Code Changes

- :art: styled: format code on config module. (_2025-01-07_)
- :test_tube: tests: edit testcase for change config attrs. (_2025-01-07_)
- :test_tube: tests: update testcase for config module. (_2025-01-07_)

### :bug: Fix Bugs

- :gear: fixed: change default log object from file to dynamic with env. (_2025-01-07_)

## 0.0.26.post0

### :sparkles: Features

- :dart: feat: add get log route on api component. (_2025-01-06_)

### :card_file_box: Documents

- :page_facing_up: docs: add more document on mkdocs. (_2025-01-06_)

### :bug: Fix Bugs

- :gear: fixed: change entrypoint in docker file. (_2025-01-06_)
- :gear: fixed: remove use PathSearch from ddeutil-io. (_2025-01-06_)

## 0.0.26

### :sparkles: Features

- :dart: feat: remove cli feature. (_2025-01-06_)

### :black_nib: Code Changes

- :test_tube: tests: add mix_stderr on the cli testcase. (_2025-01-06_)

### :card_file_box: Documents

- :page_facing_up: docs: remove docker image support. (_2025-01-06_)

## 0.0.25

### :sparkles: Features

- :dart: feat: update code on api component. (_2025-01-05_)
- :dart: feat: add default registry path on tests. (_2025-01-05_)
- :dart: feat: update cli command. (_2025-01-05_)
- :dart: feat: add release thread type for support thread timeout. (_2025-01-04_)

### :black_nib: Code Changes

- :test_tube: tests: remove cli testcase on github action. (_2025-01-04_)
- :test_tube: tests: add test cli on the github action. (_2025-01-04_)
- :test_tube: tests: update testcase for workflow release and queue object. (_2025-01-04_)
- :test_tube: test: update workflow schedule testcase to make 100 coverage. (_2025-01-04_)

### :bug: Fix Bugs

- :gear: fixed: rename of path that change on api component. (_2025-01-05_)
- :gear: fixed: change default config path that does not import when start fastapi. (_2025-01-05_)
- :gear: fixed: change name of include parameter to included. (_2025-01-04_)
- :gear: fixed: change name of exclude parameter to excluded. (_2025-01-04_)
- :gear: fixed: add double qoute on test cli command. (_2025-01-04_)
- :gear: fixed: add excluded schedule name on cli testcase. (_2025-01-04_)
- :gear: fixed: remove not use or useless methods. (_2025-01-04_)

## 0.0.24

### :sparkles: Features

- :dart: feat: add release object on workflow task release method. (_2025-01-04_)
- :dart: feat: change stop and waiting logic to schedule control func. (_2025-01-03_)
- :dart: feat: rename workflow task release func to schedule task. (_2025-01-03_)
- :dart: feat: add override_log_name argument on the workflow release method. (_2025-01-03_)
- :dart: feat: update workflow task release func. (_2025-01-03_)
- :dart: feat: change name of queue_poking method to queue. (_2025-01-01_)
- :dart: feat: rename runner function to schedule_runner. (_2025-01-01_)
- :dart: feat: change logic of workflow task data release method. (_2025-01-01_)
- :dart: feat: add logging when sleep more than 30 sec. (_2024-12-31_)
- :dart: feat: add tasks method on the workflow schedule model. (_2024-12-31_)

### :black_nib: Code Changes

- :test_tube: tests: update schedule control testcase. (_2025-01-04_)
- :construction: refactored: ⬆ bump pypa/gh-action-pypi-publish from 1.12.2 to 1.12.3 (_2025-01-01_)
- :construction: refactored: 📦 bump pydantic from 2.10.2 to 2.10.4 (_2025-01-01_)
- :test_tube: tests: update schedule tasks testcase. (_2025-01-01_)

### :card_file_box: Documents

- :page_facing_up: docs: add result and params module on mkdocs. (_2025-01-01_)

### :bug: Fix Bugs

- :gear: fixed: rename WorkflowTaskData to WorkflowTask. (_2025-01-04_)
- :gear: fixed: rename on module to cron. (_2025-01-04_)
- :gear: fixed: change variable name of queue workflow. (_2025-01-03_)
- :gear: fixed: change argument name that change on workflow_release. (_2025-01-02_)
- :gear: fixed: add queue data on scheduler task testcase. (_2024-12-31_)
- :gear: fixed: remove no cove on workflow task data. (_2024-12-31_)

## 0.0.23

### :sparkles: Features

- :dart: feat: rename schedule workflow object to workflow schedule. (_2024-12-29_)

### :black_nib: Code Changes

- :test_tube: tests: update workflow task data testcase. (_2024-12-31_)
- :test_tube: tests: update workflow schedule testcase. (_2024-12-31_)
- :test_tube: tests: update workflow poking testcase. (_2024-12-31_)
- :art: styled: add docs-string and change code format. (_2024-12-31_)
- :test_tube: tests: update testcase on workflow release. (_2024-12-31_)
- :construction: refactored: move result from utils to result module. (_2024-12-30_)
- :test_tube: tests: add more testcase for workflow. (_2024-12-30_)
- :construction: refactored: move param object from utils to params module. (_2024-12-30_)
- :test_tube: tests: add dump yaml file utils func. (_2024-12-30_)

### :bug: Fix Bugs

- :gear: fixed: remove some demo config that use on test only. (_2024-12-30_)

## 0.0.22

### :sparkles: Features

- :dart: feat: remove checking running queue on the poke method. (_2024-12-28_)
- :dart: feat: add force run flag on the poke method. (_2024-12-28_)
- :dart: feat: split queue argument validation from the release method. (_2024-12-28_)
- :dart: feat: add cutting running id func. (_2024-12-28_)
- :dart: feat: revise create result dataclass object on exec methods. (_2024-12-26_)
- :dart: feat: add check_needs method on job object for planing trigger rule. (_2024-12-25_)

### :black_nib: Code Changes

- :construction: refactored: revise result creation on workflow module. (_2024-12-27_)
- :test_tube: tests: update workflow job exec testcase. (_2024-12-24_)

### :card_file_box: Documents

- :page_facing_up: docs: update docs-string on workflow module. (_2024-12-28_)

### :bug: Fix Bugs

- :gear: fixed: move validate queue args of release method to construct method. (_2024-12-28_)
- :gear: fixed: revise validate queue arg logic. (_2024-12-28_)
- :gear: fixed: reorder code on the poke method. (_2024-12-28_)

## 0.0.21

### :sparkles: Features

- :dart: feat: add testcase for workflow exec timeout scenario. (_2024-12-24_)
- :dart: feat: revise doc-string and default value on workflow module. (_2024-12-24_)
- :dart: feat: add WORKFLOW_CORE_MAX_JOB_EXEC_TIMEOUT env variable. (_2024-12-23_)
- :dart: feat: remove result timeout from job execution method. (_2024-12-23_)
- :dart: feat: update code on job module. (_2024-12-23_)

### :black_nib: Code Changes

- :test_tube: tests: revise testcase on job module. (_2024-12-23_)
- :test_tube: tests: update job testcase on execute_strategy method. (_2024-12-23_)

### :card_file_box: Documents

- :page_facing_up: docs: add utils module for showing result context data. (_2024-12-24_)
- :page_facing_up: docs: update workflow doc-string and update mkdocs content. (_2024-12-23_)

## 0.0.20

### :sparkles: Features

- :dart: feat: prepare argument of release method of workflow object. (_2024-11-04_)
- :dart: feat: revision release and poke method on workflow object. (_2024-11-04_)
- :dart: feat: add iden property on stage model. (_2024-11-02_)
- :dart: feat: move workflow data dataclass from schedule module to workflow. (_2024-11-02_)
- :dart: feat: remove run_id field from workflow model. (_2024-11-02_)
- :dart: feat: remove run_id field from job model. (_2024-11-02_)
- :dart: feat: remove run_id field from stage model. (_2024-11-02_)
- :dart: feat: split workflow object from schedule module. (_2024-11-01_)
- :dart: feat: add end date in poke method. (_2024-11-01_)
- :dart: feat: adjust result from workflow release. (_2024-10-31_)
- :dart: feat: remove running queue on workflow control function. (_2024-10-31_)
- :dart: feat: prepare logic of workflow task data. (_2024-10-31_)
- :dart: feat: add logger instance on conf module. (_2024-10-31_)

### :black_nib: Code Changes

- :test_tube: tests: update the stage testcase. (_2024-12-22_)
- :construction: refactored: rename create sh file on the bash stage object. (_2024-12-22_)
- :construction: refactored: 📦 bump typer from 0.14.0 to 0.15.1 (_2024-12-10_)
- :construction: refactored: ⬆ bump pypa/gh-action-pypi-publish from 1.11.0 to 1.12.2 (_2024-12-01_)
- :construction: refactored: ⬆ bump codecov/codecov-action from 4 to 5 (_2024-12-01_)
- :construction: refactored: 📦 update typer requirement from <1.0.0,==0.12.5 to ==0.14.0 (_2024-12-01_)
- :construction: refactored: 📦 bump pydantic from 2.9.2 to 2.10.2 (_2024-12-01_)
- :test_tube: tests: update testcase for schedule. (_2024-11-06_)
- :test_tube: tests: fix testcase for workflow object. (_2024-11-04_)
- :construction: refactored: ⬆ bump pypa/gh-action-pypi-publish from 1.10.2 to 1.11.0 (_2024-11-01_)
- :construction: refactored: ⬆ bump deadsnakes/action from 3.1.0 to 3.2.0 (_2024-11-01_)
- :art: styled: change valiable name on schedule module. (_2024-10-30_)

### :card_file_box: Documents

- :page_facing_up: docs: update docs for stage topic. (_2024-12-22_)
- :page_facing_up: docs: add quote on the nav for the on topic. (_2024-12-22_)

### :bug: Fix Bugs

- :gear: fixed: merge branch 'main' of https://github.com/ddeutils/ddeutil-workflow. (_2024-12-22_)
- :gear: fixed: fix run_id of workflow execute. (_2024-11-02_)
- :gear: fixed: fix list does not valid when passing to dataclass. (_2024-10-31_)

## 0.0.19

### :sparkles: Features

- :dart: feat: add validate on field in workflow and schedule workflow models. (_2024-10-30_)
- :dart: feat: add start_date argument to workflow poke method. (_2024-10-30_)
- :dart: feat: change argument on workflow release from on to cronrunner. (_2024-10-30_)
- :dart: feat: change datatype of queue and running fields on workflow task data obj. (_2024-10-30_)
- :dart: feat: remove queue args on is_pointed method in log module. (_2024-10-30_)
- :dart: feat: implement trigger rule on job model object. (_2024-10-28_)

### :black_nib: Code Changes

- :test_tube: tests: improve testcase on workflow module. (_2024-10-30_)
- :art: styled: change variable name on schedule module. (_2024-10-30_)
- :test_tube: tests: improve some testcase that do not make coverage. (_2024-10-30_)
- :art: styled: split long function of map post filter to sub-func. (_2024-10-28_)

### :card_file_box: Documents

- :page_facing_up: docs: update readme file. (_2024-10-30_)

## 0.0.18

### :sparkles: Features

- :dart: feat: improve object on init file of this package. (_2024-10-27_)

### :black_nib: Code Changes

- :test_tube: tests: updaste testcase that make 100% converage report. (_2024-10-27_)
- :test_tube: tests: add testcase support the scheduler module. (_2024-10-27_)
- :test_tube: tests: fixed cong file log testcase. (_2024-10-27_)

### :bug: Fix Bugs

- :gear: fixed: add timezone change on the gh runner. (_2024-10-27_)

### :postbox: Dependencies

- :pushpin: deps: updaste pydantic==2.9.2. (_2024-10-27_)

## 0.0.17

### :sparkles: Features

- :dart: feat: add validate for stage id that should not be duplicate. (_2024-10-26_)
- :dart: feat: merge log and config modules together. (_2024-10-26_)
- :dart: feat: remove config param object and use config instead. (_2024-10-25_)

### :black_nib: Code Changes

- :test_tube: tests: add testcase for the log module. (_2024-10-27_)
- :test_tube: tests: add testcase on the job module. (_2024-10-27_)
- :test_tube: tests: add testcase support coverage on on module. (_2024-10-26_)
- :test_tube: tests: update teatcase on utils module. (_2024-10-25_)
- :art: styled: change internal variable name on python stage object. (_2024-10-23_)

### :bug: Fix Bugs

- :gear: fixed: move cron module to vendors and ignore it in coverage process. (_2024-10-27_)

### :package: Build & Workflow

- :toolbox: build: add coverage workflow. (_2024-10-27_)
- :toolbox: build: add dockerignore and docker file multi-stage. (_2024-10-25_)
- :toolbox: build: add python nogil version on test workflow. (_2024-10-23_)

### :postbox: Dependencies

- :pushpin: deps: add toml deps package on ddeutil-io. (_2024-10-27_)

## 0.0.16

### :sparkles: Features

- :dart: feat: add default id of job if it exec standalone without workflow. (_2024-10-05_)
- :dart: feat: move all getting env var in all code to conf module. (_2024-10-02_)
- :dart: feat: change getenv config to config module. (_2024-10-01_)

### :black_nib: Code Changes

- :test_tube: tests: add testcase for param objects. (_2024-10-23_)
- :test_tube: tests: update testcase of stage module. (_2024-10-23_)
- :test_tube: tests: add testcase for make_registry func. (_2024-10-23_)
- :test_tube: tests: merge testcase together that create many files. (_2024-10-05_)
- :construction: refactored: ⬆ bump pypa/gh-action-pypi-publish from 1.10.0 to 1.10.2 (_2024-10-01_)

### :card_file_box: Documents

- :page_facing_up: docs: update desc of model fields. (_2024-10-23_)
- :page_facing_up: docs: update readme and getting started docs. (_2024-10-05_)

### :bug: Fix Bugs

- :gear: fixed: return None value if bash stage does not receive any stderr or stdout. (_2024-10-23_)
- :gear: fixed: remove un-use config object. (_2024-10-23_)
- :gear: fixed: fix type on workflow data. (_2024-10-01_)

### :package: Build & Workflow

- :toolbox: build: add docker command on build workflow. (_2024-09-30_)

### :postbox: Dependencies

- :pushpin: deps: update optional yaml on ddeutil-io. (_2024-10-23_)
- :pushpin: deps: update version of ddeutil and ddeutil-io. (_2024-10-23_)

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
