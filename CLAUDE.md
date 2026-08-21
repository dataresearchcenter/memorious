# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Behaviour rules for code agents

1. Don’t assume. Don’t hide confusion. Surface tradeoffs.
2. Minimum code that solves the problem. Nothing speculative.
3. Touch only what you must. Clean up only your own mess.
4. Define success criteria. Loop until verified.


## Build and Development Commands

**Important:** Use the project's virtualenv for all commands:
```bash
# Activate the virtualenv before running commands
source .venv/bin/activate

# Or prefix commands with the venv python
.venv/bin/python -m pytest ...
```

```bash
# Install dependencies (includes dev dependencies and all extras)
make install
# or: poetry install --with dev --all-extras

# Run tests
make test
# or: poetry run pytest -v --capture=sys --cov=memorious --cov-report lcov

# Run a single test
poetry run pytest tests/test_crawler.py -v
poetry run pytest tests/test_crawler.py::test_function_name -v

# Lint
make lint
# or: poetry run flake8 memorious

# Type checking
make typecheck
# or: poetry run mypy --strict memorious

# Pre-commit hooks
make pre-commit

# Run a crawler from a YAML config (local path or remote URI)
poetry run memorious run -c path/to/crawler.yml

# Cancel pending jobs / flush all data / show recent runs
poetry run memorious cancel -c path/to/crawler.yml
poetry run memorious flush -c path/to/crawler.yml
poetry run memorious status -c path/to/crawler.yml

# Start a standalone worker to process queued jobs (procrastinate's own CLI)
PROCRASTINATE_APP=memorious.tasks.app poetry run procrastinate worker -q memorious

# Show current runtime settings
poetry run memorious --settings

# Build the documentation (zensical, config in mkdocs.yml, output in ./site)
poetry run zensical build
# or serve it locally with live reload:
poetry run zensical serve
# `make documentation` builds and syncs the site to S3
```

## Environment Variables

Key environment variables (test defaults in pyproject.toml `[tool.pytest_env]`):

- `MEMORIOUS_BASE_PATH` - Base path for data storage
- `MEMORIOUS_INCREMENTAL` - Skip already-processed items (default: `true`); there is no CLI flag for this
- `MEMORIOUS_DEBUG` - Enable debug mode
- `MEMORIOUS_TAGS_URI` - URI for tags storage (e.g., `memory://`, `sqlite:///path/to/tags.db`)
- `MEMORIOUS_CACHE_URI` - URI for runtime cache (default: `memory://`)
- `LAKEHOUSE_URI` - URI for ftm-lakehouse archive storage
- `MEMORIOUS_MAX_RUNTIME` - Maximum crawler runtime in seconds (0 = unlimited, useful for CI time limits like GitHub Actions 6h)
- `PROCRASTINATE_DB_URI` - Database URI for job queue (e.g., `memory:`, `postgresql://...`)
- `PROCRASTINATE_APP` - Dotted path to the procrastinate app (`memorious.tasks.app`), needed by the standalone `procrastinate worker`
- `PROCRASTINATE_SYNC` - Set to `1` for synchronous execution (useful for testing)

## Architecture

Memorious is a modular web crawling framework with a pipeline-based architecture.

### Core Components

```
memorious/
├── settings.py       # Pydantic Settings configuration
├── core.py           # Cached getters: get_settings(), get_conn(), get_tags(), get_cache()
├── tasks.py          # Procrastinate task definitions (execute_stage, defer_stage)
├── cli.py            # Typer CLI with rich output
├── jobs.py           # ftm-lakehouse JobRepository accessor for crawler runs
├── model/
│   ├── crawler.py    # CrawlerConfig(Dataset) pydantic model
│   ├── stage.py      # StageConfig pydantic model + CrawlerStage runtime wrapper
│   ├── job.py        # CrawlerRunJob model
│   └── session.py    # SessionModel for HTTP session persistence
├── logic/
│   ├── context.py    # Context class passed to stage operations
│   ├── crawler.py    # Crawler wrapper class (get_crawler loads YAML by URI)
│   ├── idle_monitor.py  # Auto-stops the embedded worker when the queue is idle
│   ├── check.py      # ContextCheck URL/content validation
│   ├── fetch.py      # Standalone fetch API (fetch, FetchClient)
│   └── http.py       # httpx-based HTTP client (ContextHttp, ContextHttpResponse)
├── operations/       # Built-in stage operations
└── helpers/          # Utility functions
```

### Key Concepts

**Crawler** (`memorious/logic/crawler.py`): Loaded from YAML config files. Each crawler defines a `pipeline` of stages. Key properties: `name`, `init_stage` (entry point), `delay`, `expire`, `max_runtime`.

**Stage** (`memorious/model/stage.py`): A single step in the pipeline. Each stage has:
- `method`: Python function to execute (entry point name or `module:function`)
- `params`: Configuration passed to the method
- `handle`: Rules mapping outputs to next stages (e.g., `pass`, `fetch`, `store`)

**Context** (`memorious/logic/context.py`): Passed to every stage method. Provides:
- `emit(rule, data)` - Send data to next stage based on handler rule
- `recurse(data)` - Stage calls itself with modified data
- `http` - HTTP client with session persistence (`ContextHttp`)
- `check` - URL/content validation (`ContextCheck`)
- `store_file()`, `store_data()` - Archive storage via ftm-lakehouse
- `open()`, `local_path()` - Read content from archive by hash
- `set_tag()`, `get_tag()`, `check_tag()` - Key-value tags for incremental state
- `skip_incremental(*criteria)` - Skip if already processed (marks eagerly); `check_incremental()`/`mark_incremental()` for two-phase check/mark

The standalone fetch API (`fetch()`, `FetchClient` in `memorious/logic/fetch.py`) supports incremental skipping via a manual `cache_key` parameter: returns `None` when skipped, marks the key only after a successful response (see `docs/incremental.md`).

**Loading crawlers** (`get_crawler` in `memorious/logic/crawler.py`): Crawler YAML configs are loaded on demand from the URI or path passed to `--config`; there is no crawler registry directory.

### Job Queue (Procrastinate)

Jobs are managed via `openaleph-procrastinate`:

- `defer_stage()` creates a `DatasetJob` and defers it to the queue
- `execute_stage()` is the task handler that runs stage operations
- Standalone workers process jobs via `procrastinate worker -q memorious` (requires `PROCRASTINATE_APP=memorious.tasks.app`); `memorious run` embeds its own worker
- Supports sync mode for testing (`PROCRASTINATE_SYNC=1`, `PROCRASTINATE_DB_URI=memory:`)

### Storage Architecture

- **Archive** (`context.archive`): ftm-lakehouse for permanent file storage (HTTP responses, documents)
- **Cache** (`context.cache`): anystore memory/redis cache for runtime state (HTTP sessions)
- **Tags** (`context.tags`): anystore Tags for incremental crawl state

### Built-in Operations

Operations are registered via the `@register` decorator in `memorious/operations/`. Use `module:function` syntax for custom operations (e.g., `mypackage.ops:my_func` or `./src/ops.py:my_func`).

- **Initializers** (`initializers.py`): `init`, `seed`, `sequence`, `dates`, `enumerate`, `tee`
- **Fetch** (`fetch.py`): `fetch`, `session`, `post`, `post_json`, `post_form`
- **Parse** (`parse.py`): `parse`, `parse_listing`, `parse_jq`, `parse_csv`, `parse_xml`
- **Store** (`store.py`): `store`, `directory`, `lakehouse`, `cleanup_archive`
- **Extract** (`extract.py`): `extract` (text/metadata extraction)
- **Clean** (`clean.py`): `clean`, `clean_html`
- **Regex** (`regex.py`): `regex_groups`
- **Debug** (`debug.py`): `inspect`, `ipdb`
- **FTP/WebDAV** (`ftp.py`, `webdav.py`): `ftp_fetch`, `dav_index`
- **Aleph** (`aleph.py`): `aleph_emit`, `aleph_emit_document`, `aleph_folder`, `aleph_emit_entity`
- **FTM** (`ftm.py`): `ftm_store`, `ftm_load_aleph`
- **DocumentCloud** (`documentcloud.py`): `documentcloud_query`, `documentcloud_mark_processed`

### Crawler YAML Structure

```yaml
name: crawler_name
description: "Description"
schedule: weekly  # informational only (disabled, hourly, daily, weekly, monthly)
init: init  # entry stage name
max_runtime: 21600  # optional: max runtime in seconds (e.g., 6h for GitHub Actions)

pipeline:
  init:
    method: seed
    params:
      urls: [https://example.com]
    handle:
      pass: fetch

  fetch:
    method: fetch
    params:
      rules: {domain: example.com}
    handle:
      pass: parse

  parse:
    method: parse
    params:
      store: {mime_group: documents}
    handle:
      store: store
      fetch: fetch

  store:
    method: lakehouse  # or: directory
```

### Rules System

Rules filter URLs/content in fetch and parse stages. Defined in `memorious/helpers/rule.py`:
- `domain`, `mime_type`, `mime_group`, `pattern` (regex)
- Boolean: `and`, `or`, `not`, `match_all`

## Dependencies

Key dependencies:
- `httpx` - HTTP client (replaced requests)
- `typer` + `rich` - CLI (replaced click + tabulate)
- `pydantic-settings` - Configuration management
- `anystore` - Storage abstraction and tags
- `ftm-lakehouse` - Archive storage
- `openaleph-procrastinate` - Job queue (PostgreSQL-based)
- `ftmq` - FollowTheMoney query utilities

## Testing

Tests use pytest with these fixtures:
- `httpbin` - pytest-httpbin provides a local HTTP test server
- Test config in `tests/testdata/config/`
- Test data output in `tests/testdata/data/`
- Procrastinate runs in sync mode with in-memory DB for tests
