# Operations

Operations are the building blocks of crawler pipelines. Each stage executes an operation that processes data and emits results to subsequent stages.

## Built-in Operations

### Initializers

Start your pipeline with seed data:

| Operation | Description |
|-----------|-------------|
| `seed` | Emit URLs from a list |
| `sequence` | Generate a sequence of numbers |
| `dates` | Generate a sequence of dates |
| `enumerate` | Emit items from a list |
| `tee` | Pass data through unchanged |

### Fetching

Make HTTP requests:

| Operation | Description |
|-----------|-------------|
| `fetch` | HTTP GET request |
| `post` | HTTP POST request |
| `post_json` | POST with JSON body |
| `post_form` | POST with form data |
| `session` | Configure HTTP session (auth, proxy) |
| `ftp_fetch` | FTP file listing |
| `dav_index` | WebDAV directory listing |

### Parsing

Extract data from responses:

| Operation | Description |
|-----------|-------------|
| `parse` | Parse HTML, extract links |
| `parse_jq` | Query JSON with jq |
| `parse_csv` | Parse CSV files |
| `parse_xml` | Parse XML documents |
| `parse_listing` | Parse directory listings |

### Processing

Transform and clean data:

| Operation | Description |
|-----------|-------------|
| `clean_html` | Clean HTML content |
| `extract` | Extract files from archives |
| `regex_groups` | Extract data with regex |

### Storage

Save crawled data:

| Operation | Description |
|-----------|-------------|
| `directory` | Save to local directory |
| `store` | Save to archive storage |
| `lakehouse` | Save to ftm-lakehouse |
| `ftm_store` | Store FTM entities |
| `aleph_emit_document` | Upload to Aleph |
| `aleph_emit_entity` | Create Aleph entity |

### Debug

Development helpers:

| Operation | Description |
|-----------|-------------|
| `inspect` | Log data to console |
| `ipdb` | Drop into debugger |

## Using Operations

Reference by name in your crawler YAML:

```yaml
pipeline:
  fetch:
    method: fetch
    params:
      retry: 3
    handle:
      pass: parse
```

## Writing Custom Operations

Create a Python function that receives a context and data dict:

```python
def my_operation(context, data):
    """Process data and emit results."""
    url = data.get("url")
    context.log.info("Processing", url=url)

    result = do_something(data)
    context.emit(data=result)
```

Reference with `module:function` syntax:

```yaml
process:
  method: mypackage.ops:my_operation
  params:
    my_param: value
```

### The Context Object

| Attribute | Description |
|-----------|-------------|
| `context.params` | Stage parameters |
| `context.crawler` | Crawler instance |
| `context.log` | Structured logger |
| `context.http` | HTTP client |
| `context.emit(data)` | Emit to next stage |
| `context.recurse(data)` | Re-queue current stage |
| `context.check_tag(key)` | Check incremental tag |
| `context.set_tag(key, val)` | Set incremental tag |
| `context.store_file(path)` | Store file in archive |

### Making HTTP Requests

```python
def fetch_api(context, data):
    result = context.http.get(data["url"])
    if result.ok:
        context.emit(data={**data, "json": result.json})
```

### Incremental Crawling

```python
def my_operation(context, data):
    url = data["url"]
    if context.check_tag(url):
        return  # Skip, already processed

    result = process(data)
    context.set_tag(url, True)
    context.emit(data=result)
```

### Registering Operations

For reusable operations, register them with a name:

```python
from memorious.operations import register

@register("my_fetch")
def my_fetch(context, data):
    # Now available as method: my_fetch
    context.emit(data=data)
```

## Next Steps

- [Operations Reference](reference/operations.md) - Full API documentation
- [Crawlers](crawler.md) - How to configure crawlers
