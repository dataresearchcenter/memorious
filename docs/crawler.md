# Crawlers

A crawler is a YAML configuration that defines a data processing pipeline. Each crawler is made up of **stages** that process data and pass it to subsequent stages.

## Basic Structure

```yaml
name: my_crawler
description: A simple web crawler
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
      pass: parse

  parse:
    method: parse
    handle:
      pass: store

  store:
    method: directory
    params:
      path: ./output
```

## Crawler Options

| Option | Type | Description |
|--------|------|-------------|
| `name` | string | Unique identifier for the crawler |
| `description` | string | Human-readable description |
| `delay` | int | Default delay between tasks (seconds) |
| `expire` | int | Days until cached data expires |
| `stealthy` | bool | Use random User-Agent headers |

## Stages

Each stage has:

- `method`: The operation to execute (built-in name or `module:function`)
- `params`: Parameters passed to the operation
- `handle`: Routing rules for the next stage

### Handlers

Handlers define which stage runs next based on the operation's output:

```yaml
parse:
  method: parse
  handle:
    fetch: fetch   # URLs to crawl go to fetch stage
    store: store   # Documents go to store stage
    pass: next     # Default handler
```

Common handler names:

- `pass` - Default success handler
- `fetch` - URLs that need fetching
- `store` - Data ready for storage

## Running Crawlers

```bash
# Run synchronously (waits for completion)
memorious run my_crawler.yml

# Queue for background workers
memorious start my_crawler.yml

# Run with custom Python modules
memorious run my_crawler.yml --src ./src

# Incremental mode (skip already-processed items)
memorious run my_crawler.yml --incremental
```

## Common Patterns

### Recursive Web Crawling

```yaml
name: web_crawler
pipeline:
  init:
    method: seed
    params:
      urls:
        - https://example.com/page1
        - https://example.com/page2
    handle:
      pass: fetch

  fetch:
    method: fetch
    handle:
      pass: parse

  parse:
    method: parse
    params:
      rules:
        domain: example.com
      store:
        mime_group: documents
    handle:
      fetch: fetch   # Recursive: parse -> fetch -> parse
      store: store

  store:
    method: directory
    params:
      path: ./downloads
```

### API Pagination

```yaml
name: api_crawler
pipeline:
  init:
    method: sequence
    params:
      start: 1
      stop: 100
    handle:
      pass: seed

  seed:
    method: seed
    params:
      url: https://api.example.com/items?page=%(number)s
    handle:
      pass: fetch

  fetch:
    method: fetch
    handle:
      pass: parse

  parse:
    method: parse_jq
    params:
      query: .items[]
    handle:
      pass: store

  store:
    method: directory
    params:
      path: ./output
```

### Date Range Crawling

```yaml
name: date_crawler
pipeline:
  init:
    method: dates
    params:
      begin: "2024-01-01"
      end: "2024-12-31"
      days: 1
    handle:
      pass: seed

  seed:
    method: seed
    params:
      url: https://example.com/data/%(date)s
    handle:
      pass: fetch
  # ... rest of pipeline
```

## Rules

Rules filter which URLs are processed or stored:

```yaml
parse:
  method: parse
  params:
    # Only follow links matching these rules
    rules:
      and:
        - domain: example.com
        - not:
            pattern: ".*/login.*"

    # Only store documents
    store:
      mime_group: documents
```

### Available Rules

| Rule | Description |
|------|-------------|
| `domain` | Match URLs from a domain |
| `pattern` | Regex pattern for URLs |
| `mime_type` | Exact MIME type match |
| `mime_group` | MIME type group (`documents`, `images`, `web`, etc.) |
| `xpath` | Match if XPath finds elements |

Combine with `and`, `or`, `not`:

```yaml
rules:
  and:
    - domain: example.com
    - not:
        or:
          - mime_group: images
          - pattern: ".*\\.css$"
```

## Incremental Crawling

Skip already-processed items using tags:

```yaml
name: incremental_crawler
expire: 7  # Remember items for 7 days
pipeline:
  fetch:
    method: fetch
    params:
      skip_incremental: true  # Skip if already fetched
```

Or in custom operations:

```python
def my_operation(context, data):
    url = data.get("url")
    if context.check_tag(url):
        return  # Already processed

    # Process...
    context.set_tag(url, True)
    context.emit(data=result)
```

## Postprocessing

Run a function after the crawler completes:

```yaml
name: my_crawler
pipeline:
  # ... stages ...
aggregator:
  method: mymodule:export_results
  params:
    output_file: results.json
```

## Debugging

Use the `inspect` operation to log data:

```yaml
debug:
  method: inspect  # Logs the data dict
```

Use sampling to test with a subset of data:

```yaml
fetch:
  method: fetch
  params:
    sampling_rate: 0.1  # Only process 10% of items
```

## Next Steps

- [Operations](operations.md) - Available operations
- [Crawler Reference](reference/crawler.md) - Complete configuration reference
- [Operations Reference](reference/operations.md) - API documentation
