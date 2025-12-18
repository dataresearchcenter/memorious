# Installation

## From PyPI

```bash
pip install memorious
```

## From Source

```bash
git clone https://github.com/dataresearchcenter/memorious.git
cd memorious
pip install -e .
```

## Optional Dependencies

Memorious has optional dependencies for specific features:

```bash
# SQL database support (SQLite, PostgreSQL)
pip install memorious[sql]

# PostgreSQL with psycopg2
pip install memorious[postgres]

# Redis support
pip install memorious[redis]

# FTP support
pip install memorious[ftp]
```

## Verify Installation

```bash
memorious --version
```

## Environment Setup

Memorious is configured via environment variables. Create a `.env` file or export them:

```bash
# Base directory for data storage
export MEMORIOUS_BASE_PATH=./data

# Enable debug logging
export MEMORIOUS_DEBUG=true
```

### Development Setup

For local development and testing, in-memory storage works out of the box:

```bash
export MEMORIOUS_BASE_PATH=./data
export MEMORIOUS_CACHE_URI=memory://
export PROCRASTINATE_DB_URI=memory:
export PROCRASTINATE_SYNC=1
```

### Production Setup

For production with multiple workers:

```bash
# Core
export MEMORIOUS_BASE_PATH=/var/lib/memorious

# Redis for shared cache
export MEMORIOUS_CACHE_URI=redis://localhost:6379/0

# PostgreSQL for job queue and tags
export MEMORIOUS_TAGS_URI=postgresql://user:pass@localhost/memorious
export PROCRASTINATE_DB_URI=postgresql://user:pass@localhost/memorious
```

See the [Settings Reference](reference/settings.md) for all configuration options.
