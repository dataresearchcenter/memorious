[![Docs](https://img.shields.io/badge/docs-live-brightgreen)](https://docs.investigraph.dev/lib/memorious/)
[![memorious4 on pypi](https://img.shields.io/pypi/v/memorious4)](https://pypi.org/project/memorious4/)
[![PyPI Downloads](https://static.pepy.tech/badge/memorious4/month)](https://pepy.tech/projects/memorious4)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/memorious4)](https://pypi.org/project/memorious4/)
[![Python test and package](https://github.com/dataresearchcenter/memorious/actions/workflows/python.yml/badge.svg)](https://github.com/dataresearchcenter/memorious/actions/workflows/python.yml)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Coverage Status](https://coveralls.io/repos/github/dataresearchcenter/memorious/badge.svg?branch=main)](https://coveralls.io/github/dataresearchcenter/memorious?branch=main)
[![AGPLv3+ License](https://img.shields.io/pypi/l/memorious4)](./LICENSE)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)

# Memorious

A light-weight web scraping toolkit for Python.

!!! Info
    This is a hard fork of the [original memorious project](https://github.com/alephdata/memorious) that was discontinued in 2023. To avoid pypi naming conflict, this package is called `memorious4`

    `pip install memorious4`

    See [development section](./development.md) for what has changed since.

## Features

- **Modular pipelines** - Compose crawlers from reusable stages
- **Built-in operations** - Fetch, parse, store, and more
- **Incremental crawling** - Skip already-processed items
- **HTTP caching** - Conditional requests with ETag support
- **OpenAleph integration** - Push data to [OpenAleph](https://openaleph.org) instances
- **FTM support** - Extract and store [FollowTheMoney](https://followthemoney.tech) entities

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
