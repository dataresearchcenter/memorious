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

- **Entry point name**: `fetch`, `parse`, `store`
- **Module path**: `memorious.operations.fetch:fetch`
- **Custom module**: `myproject.operations:custom_fetch`

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
