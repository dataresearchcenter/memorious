# Operations Reference

Operations are the building blocks of memorious crawlers. Each stage in a
crawler pipeline executes an operation that processes data and optionally
emits results to subsequent stages.

## How to Use Operations

Operations are referenced by name in the `method` field of a pipeline stage:

```yaml
pipeline:
  fetch:
    method: fetch  # Uses the 'fetch' operation
    params:
      retry: 5
    handle:
      pass: parse
```

Operations can be referenced by:

- **Registered name**: `fetch`, `parse`, `store` (built-in operations)
- **Custom module path**: `myproject.operations:custom_fetch`

---

## Writing Custom Operations

You can create custom operations for your crawlers. An operation is a function
that receives a `Context` object and a data dictionary, and optionally emits
data to subsequent stages.

### Basic Structure

```python
from memorious.logic.context import Context

def my_operation(context: Context, data: dict) -> None:
    """Process data and emit results."""
    # Access stage parameters
    param_value = context.params.get("my_param", "default")

    # Log progress
    context.log.info("Processing", url=data.get("url"))

    # Process data
    result = do_something(data)

    # Emit to next stage
    context.emit(data=result)
```

### Using in a Crawler

Reference your custom operation using `module:function` syntax:

```yaml
name: my_crawler
pipeline:
  init:
    method: seed
    params:
      url: https://example.com
    handle:
      pass: fetch

  fetch:
    method: fetch
    handle:
      pass: process

  process:
    method: myproject.operations:my_operation
    params:
      my_param: value
    handle:
      pass: store
```

### The Context Object

The `Context` provides access to crawler state and utilities:

| Attribute/Method | Description |
|------------------|-------------|
| `context.params` | Stage parameters from YAML config |
| `context.crawler` | The Crawler instance |
| `context.stage` | Current CrawlerStage |
| `context.run_id` | Unique identifier for this crawl run |
| `context.log` | Structured logger (structlog) |
| `context.http` | HTTP client for making requests |
| `context.emit(data, rule)` | Emit data to next stage |
| `context.recurse(data, delay)` | Re-queue current stage |
| `context.get(key, default)` | Get param with env var expansion |
| `context.store_file(path)` | Store file in archive |
| `context.store_data(data)` | Store bytes in archive |
| `context.check_tag(tag)` | Check if tag exists (incremental) |
| `context.set_tag(tag, value)` | Set tag value (incremental) |

### Emitting Data

Use `context.emit()` to pass data to subsequent stages:

```python
# Emit to default handler (pass)
context.emit(data={"url": "https://example.com/page"})

# Emit to specific handler
context.emit(rule="store", data={"content_hash": hash})

# Optional emit (doesn't error if handler missing)
context.emit(data=data, optional=True)
```

### Working with HTTP

Access the HTTP client via `context.http`:

```python
def fetch_api(context: Context, data: dict) -> None:
    url = data.get("url")

    # GET request
    result = context.http.get(url)

    # Access response
    if result.ok:
        json_data = result.json
        context.emit(data={**data, **json_data})

    # POST with JSON
    result = context.http.post(url, json_data={"query": "test"})

    # POST with form data
    result = context.http.post(url, data={"field": "value"})
```

### Incremental Crawling

Support incremental crawling to skip already-processed items:

```python
def my_operation(context: Context, data: dict) -> None:
    url = data.get("url")

    # Check if already processed
    if context.check_tag(url):
        context.log.info("Skipping (already processed)", url=url)
        return

    # Process data...
    result = process(data)

    # Mark as processed
    context.set_tag(url, True)

    context.emit(data=result)
```

### Error Handling

Handle errors gracefully:

```python
def my_operation(context: Context, data: dict) -> None:
    try:
        result = process(data)
        context.emit(data=result)
    except ValueError as e:
        # Log warning and continue
        context.emit_warning("Processing failed", error=str(e))
    except Exception as e:
        # Log error - this will stop the crawler unless continue_on_error is set
        context.log.error("Fatal error", error=str(e))
        raise
```

### Registering Operations (Advanced)

For reusable operations across multiple projects, you can register them
in the memorious operations registry:

```python
from memorious.operations import register

@register("my_custom_fetch")
def my_custom_fetch(context, data):
    """Custom fetch operation available as 'my_custom_fetch'."""
    # Implementation...
    context.emit(data=data)
```

After registration, use it by name in YAML:

```yaml
pipeline:
  fetch:
    method: my_custom_fetch  # No module path needed
```

Note: Registration happens at import time, so ensure your module is imported
before the crawler runs. You can do this by importing it in your package's
`__init__.py` or using the `--src` CLI option.

---

## Initializer Operations

Operations for starting crawler pipelines and generating initial data.

::: memorious.operations.initializers.seed

::: memorious.operations.initializers.enumerate

::: memorious.operations.initializers.tee

::: memorious.operations.initializers.sequence

::: memorious.operations.initializers.dates

---

## Fetch Operations

Operations for making HTTP requests.

::: memorious.operations.fetch.fetch

::: memorious.operations.fetch.session

::: memorious.operations.fetch.post

::: memorious.operations.fetch.post_json

::: memorious.operations.fetch.post_form

---

## Parse Operations

Operations for parsing HTML, XML, JSON, and CSV content.

::: memorious.operations.parse.parse

::: memorious.operations.parse.parse_listing

::: memorious.operations.parse.parse_jq

::: memorious.operations.parse.parse_csv

::: memorious.operations.parse.parse_xml

---

## Clean Operations

Operations for cleaning and validating data.

::: memorious.operations.clean.clean

::: memorious.operations.clean.clean_html

---

## Extract Operations

Operations for extracting files from compressed archives.

::: memorious.operations.extract.extract

---

## Regex Operations

Operations for extracting structured data using regular expressions.

::: memorious.operations.regex.regex_groups

---

## Store Operations

Operations for storing crawled files.

::: memorious.operations.store.store

::: memorious.operations.store.directory

::: memorious.operations.store.lakehouse

::: memorious.operations.store.cleanup_archive

---

## Debug Operations

Operations for debugging crawlers during development.

::: memorious.operations.debug.inspect

::: memorious.operations.debug.ipdb

---

## Helper Modules

These modules provide utility functions used by operations.

### Pagination

::: memorious.helpers.pagination
    options:
      show_root_heading: true
      members:
        - get_paginated_url
        - paginate

### Casting

::: memorious.helpers.casting
    options:
      show_root_heading: true
      members:
        - cast_value
        - cast_dict
        - ensure_date

### XPath

::: memorious.helpers.xpath
    options:
      show_root_heading: true
      members:
        - extract_xpath

### Template

::: memorious.helpers.template
    options:
      show_root_heading: true
      members:
        - render_template

### Forms

::: memorious.helpers.forms
    options:
      show_root_heading: true
      members:
        - extract_form

### Regex

::: memorious.helpers.regex
    options:
      show_root_heading: true
      members:
        - regex_first

### YAML

::: memorious.helpers.yaml
    options:
      show_root_heading: true
      members:
        - load_yaml
        - IncludeLoader

---

## Advanced: Incremental Crawling

The incremental module provides advanced skip logic for efficient crawling.

::: memorious.logic.incremental
    options:
      show_root_heading: true
      members:
        - should_skip_incremental
        - mark_incremental_complete
