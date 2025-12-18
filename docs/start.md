# Quick Start

Get up and running with Memorious in minutes.

## Install

```bash
pip install memorious
```

## Create a Crawler

Create a file called `my_crawler.yml`:

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
      pass: parse

  parse:
    method: parse
    params:
      store:
        mime_group: documents
    handle:
      fetch: fetch
      store: store

  store:
    method: directory
    params:
      path: ./output
```

This crawler:

1. Starts with a seed URL
2. Fetches the page
3. Parses it for links and documents
4. Recursively fetches linked pages
5. Stores documents to the `./output` directory

## Run It

```bash
memorious run my_crawler.yml
```

## What's Next?

- [Installation](installation.md) - Installation options and environment setup
- [Crawlers](crawler.md) - Learn how to configure crawlers
- [Operations](operations.md) - Explore available operations
- [CLI Reference](reference/cli.md) - All CLI commands
