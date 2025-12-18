# Installation

Memorious can be installed directly via pip and run from the command line.

## Quick Start

```bash
# Install memorious
pip install memorious

# Run a crawler
memorious run path/to/crawler.yml
```

## Installation Options

### From PyPI

```bash
pip install memorious
```

### From Source

```bash
git clone https://github.com/alephdata/memorious.git
cd memorious
pip install -e .
```

## Running a Crawler

Crawlers are defined in YAML configuration files. To run a crawler:

```bash
memorious run my_crawler.yml
```

If your crawler uses custom Python modules, use the `--src` option to add them to the Python path:

```bash
memorious run my_crawler.yml --src ./src
```

See the [CLI Reference](cli.md) for all available commands.

## Environment Variables

Your Memorious instance is configured by environment variables. For a complete list, see the [Settings Reference](reference/settings.md).

### Quick Reference

**Core Settings:**

- `MEMORIOUS_BASE_PATH`: base directory for data storage (default: `./data`)
- `MEMORIOUS_DEBUG`: enable debug mode (default: `false`)
- `MEMORIOUS_INCREMENTAL`: enable incremental crawling (default: `true`)
- `MEMORIOUS_EXPIRE`: days until cached data expires (default: `1`)

**HTTP Settings:**

- `MEMORIOUS_HTTP_RATE_LIMIT`: max HTTP requests per host per minute (default: `120`)
- `MEMORIOUS_HTTP_CACHE`: enable HTTP response caching (default: `true`)
- `MEMORIOUS_USER_AGENT`: custom User-Agent string

**Storage Settings:**

- `MEMORIOUS_CACHE_URI`: URI for runtime cache (default: `memory://`)
- `MEMORIOUS_TAGS_URI`: URI for tags/incremental state storage
- `LAKEHOUSE_URI`: base URI for archive storage (default: `./data`)

**Job Queue:**

- `PROCRASTINATE_DB_URI`: database URI for job queue (default: `memory:`)

**Integrations:**

- `FTM_STORE_URI`: database URI for FTM entity storage
- `ALEPH_HOST`: Aleph instance URL
- `ALEPH_API_KEY`: API key for Aleph authentication

## Production Deployment

For production deployments with multiple workers, you'll need:

1. **PostgreSQL** for the job queue (`PROCRASTINATE_DB_URI`)
2. **Redis** (optional) for shared cache across workers (`MEMORIOUS_CACHE_URI`)

Example production configuration:

```bash
export MEMORIOUS_BASE_PATH=/var/lib/memorious
export MEMORIOUS_CACHE_URI=redis://localhost:6379/0
export MEMORIOUS_TAGS_URI=postgresql://user:pass@localhost/memorious
export PROCRASTINATE_DB_URI=postgresql://user:pass@localhost/memorious
```

Start a worker to process crawler jobs:

```bash
memorious worker --concurrency 4
```

## Building a Crawler

Check out the [reference documentation](reference.md) to learn how to build your own crawlers.
