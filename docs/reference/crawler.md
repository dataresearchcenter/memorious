# Crawler Reference

Complete reference for crawler YAML configuration.

## Top-Level Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | required | Unique identifier for the crawler |
| `description` | string | `None` | Human-readable description |
| `delay` | int | `0` | Default delay between tasks (seconds) |
| `expire` | int | `1` | Days until cached data expires |
| `max_runtime` | int | `0` | Maximum runtime in seconds (0 = unlimited). See [Runtime Control](#runtime-control) |
| `stealthy` | bool | `false` | Use random User-Agent headers |

## Runtime Control

### Max Runtime

The `max_runtime` option limits how long a crawler can run. This is useful for CI environments with time limits (e.g., GitHub Actions 6-hour limit).

```yaml
name: my_crawler
max_runtime: 21600  # 6 hours in seconds
```

When using `memorious run`:

- A timer starts when the crawler begins
- When `max_runtime` is exceeded, SIGTERM is sent to stop the worker
- Pending jobs are skipped (checked before each stage execution)
- The crawler exits gracefully, flushing any pending entity data

Can also be set globally via `MEMORIOUS_MAX_RUNTIME` environment variable.

### Error Handling

When a stage raises an exception:

- **With `--continue-on-error`**: The error is logged and execution continues with other jobs
- **Without `--continue-on-error`** (default): The crawler stops immediately by:
    1. Sending SIGTERM to terminate the worker process
    2. Pending jobs remain in the queue but are not processed

### Clearing Previous Runs

By default, `memorious run` cancels any pending jobs from previous runs before starting. Control this with `--clear-runs` / `--no-clear-runs`:

```bash
# Default: cancel previous jobs before starting
memorious run crawler.yml

# Keep previous jobs in queue (resume interrupted crawl)
memorious run crawler.yml --no-clear-runs
```

### Cancel vs Stop

The crawler has two termination methods:

- **`cancel()`**: Removes pending jobs from the queue. Used by `memorious cancel` CLI command.
- **`stop()`**: Sends SIGTERM to terminate the current worker process. Used internally on unhandled errors.

## Pipeline

The `pipeline` key defines the crawler stages:

```yaml
pipeline:
  stage_name:
    method: operation_name
    params:
      key: value
    handle:
      pass: next_stage
```

### Stage Configuration

| Option | Type | Description |
|--------|------|-------------|
| `method` | string | Operation name or `module:function` path |
| `params` | dict | Parameters passed to the operation |
| `handle` | dict | Handler routing (rule → stage name) |

### Handlers

Handlers route data to subsequent stages based on the operation's output:

| Handler | Description |
|---------|-------------|
| `pass` | Default success handler |
| `fetch` | URLs that need fetching |
| `store` | Data ready for storage |
| `fragment` | FTM entity fragments |

Custom handlers can be defined by operations.

## Rules

Rules filter HTTP responses based on URL, content type, or document structure.

### Rule Types

| Rule | Description | Example |
|------|-------------|---------|
| `domain` | Match URLs from a domain (including subdomains) | `example.com` |
| `pattern` | Match URL against a regex pattern | `.*\.pdf$` |
| `mime_type` | Match exact MIME type | `application/pdf` |
| `mime_group` | Match MIME type group | `documents` |
| `xpath` | Match if XPath finds elements | `//div[@class="article"]` |
| `match_all` | Always matches (default) | `{}` |

### MIME Groups

| Group | Description |
|-------|-------------|
| `web` | HTML, CSS, JavaScript |
| `images` | Image files |
| `media` | Audio and video |
| `documents` | PDF, Office documents, text |
| `archives` | ZIP, TAR, compressed files |
| `assets` | Fonts, icons, other assets |

### Boolean Operators

Combine rules using `and`, `or`, and `not`:

```yaml
# Match PDFs from example.com
rules:
  and:
    - domain: example.com
    - mime_type: application/pdf

# Match documents but not images
rules:
  and:
    - mime_group: documents
    - not:
        mime_group: images

# Match either domain
rules:
  or:
    - domain: example.com
    - domain: example.org
```

### Complex Example

```yaml
parse:
  method: parse
  params:
    rules:
      and:
        - domain: dataresearchcenter.org
        - not:
            or:
              - domain: vis.dataresearchcenter.org
              - domain: data.dataresearchcenter.org
              - mime_group: images
              - pattern: ".*/about.*"
    store:
      mime_group: documents
  handle:
    fetch: fetch
    store: store
```

## Aggregator

Run postprocessing after the crawler completes:

```yaml
aggregator:
  method: module:function
  params:
    key: value
```

The aggregator function receives a context object with access to crawler state.

## Context Object

Operations receive a `Context` object with these attributes:

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `context.crawler` | `Crawler` | The crawler instance |
| `context.stage` | `CrawlerStage` | Current stage |
| `context.run_id` | `str` | Unique run identifier |
| `context.params` | `dict` | Stage parameters |
| `context.log` | `Logger` | Structured logger (structlog) |
| `context.http` | `ContextHttp` | HTTP client |

### Methods

| Method | Description |
|--------|-------------|
| `emit(data, rule='pass', optional=False)` | Emit data to next stage |
| `recurse(data, delay=None)` | Re-queue current stage |
| `get(key, default=None)` | Get param with env var expansion |
| `store_file(path)` | Store file in archive, returns content hash |
| `store_data(data, encoding='utf-8')` | Store bytes in archive |
| `check_tag(tag)` | Check if tag exists |
| `get_tag(tag)` | Get tag value |
| `set_tag(tag, value)` | Set tag value |
| `skip_incremental(*criteria)` | Check/set incremental skip |
| `emit_warning(message, **kwargs)` | Log a warning |

## HTTP Client

The `context.http` client provides:

### Methods

```python
context.http.get(url, **kwargs)
context.http.post(url, **kwargs)
context.http.rehash(data)  # Restore response from serialized data
context.http.save()        # Persist session state
context.http.reset()       # Clear session state
```

### Proxy Configuration

Proxies can be configured globally via `MEMORIOUS_HTTP_PROXIES` or per-stage:

```yaml
pipeline:
  fetch:
    method: fetch
    params:
      # Single proxy
      http_proxies: http://proxy:8080

      # Multiple proxies (random selection per request)
      http_proxies:
        - http://proxy1:8080
        - http://proxy2:8080
        - socks5://proxy3:1080
```

Stage-level `http_proxies` overrides the global setting. When multiple proxies are provided, a random one is selected when the HTTP client is created.

### Request Parameters

| Parameter | Description |
|-----------|-------------|
| `headers` | Extra HTTP headers |
| `auth` | Tuple of (username, password) |
| `data` | Form data for POST |
| `json_data` | JSON body for POST |
| `params` | URL query parameters |
| `lazy` | Defer the actual request |
| `timeout` | Request timeout in seconds |

### Response Properties

| Property | Description |
|----------|-------------|
| `url` | Final URL after redirects |
| `status_code` | HTTP status code |
| `headers` | Response headers |
| `encoding` | Content encoding |
| `content_hash` | SHA1 hash of body |
| `content_type` | Normalized MIME type |
| `file_name` | From Content-Disposition |
| `ok` | True if status < 400 |
| `raw` | Body as bytes |
| `text` | Body as string |
| `html` | Parsed lxml HTML tree |
| `xml` | Parsed lxml XML tree |
| `json` | Parsed JSON |
| `retrieved_at` | ISO timestamp |
| `last_modified` | From Last-Modified header |

### Response Methods

| Method | Description |
|--------|-------------|
| `local_path()` | Context manager for local file path |
| `serialize()` | Convert to dict for passing between stages |
| `close()` | Close the connection |

## Data Validation

Context validation helpers:

| Helper | Description |
|--------|-------------|
| `is_not_empty(value)` | Check value is not empty |
| `is_numeric(value)` | Check value is numeric |
| `is_integer(value)` | Check value is an integer |
| `match_date(value)` | Check value is a date |
| `match_regexp(value, pattern)` | Check value matches regex |
| `has_length(value, length)` | Check value has given length |
| `must_contain(value, substring)` | Check value contains string |

## Debugging

### Debug Operation

```yaml
debug:
  method: inspect
```

### Sampling Rate

Process only a subset of data during development:

```yaml
fetch:
  method: fetch
  params:
    sampling_rate: 0.1  # Process 10% of items
```

### Interactive Debugger

```yaml
debug:
  method: ipdb  # Drops into ipdb debugger
```
