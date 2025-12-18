# Memorious

A light-weight web scraping toolkit for Python.

## Features

- **Modular pipelines** - Compose crawlers from reusable stages
- **Built-in operations** - Fetch, parse, store, and more
- **Incremental crawling** - Skip already-processed items
- **HTTP caching** - Conditional requests with ETag support
- **Aleph integration** - Push data to Aleph instances
- **FTM support** - Store FollowTheMoney entities

## Quick Example

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
      pass: store

  store:
    method: directory
    params:
      path: ./output
```

```bash
pip install memorious
memorious run my_crawler.yml
```

## Documentation

<div class="grid cards" markdown>

- [Quick Start](start.md) - Get up and running in minutes
- [Installation](installation.md) - Installation and setup
- [Crawlers](crawler.md) - How to configure crawlers
- [Operations](operations.md) - Available operations

</div>

## Reference

- [CLI Reference](reference/cli.md) - Command-line interface
- [Crawler Reference](reference/crawler.md) - Configuration options
- [Operations Reference](reference/operations.md) - API documentation
- [Settings Reference](reference/settings.md) - Environment variables
