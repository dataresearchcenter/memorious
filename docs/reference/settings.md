# Settings Reference

Memorious uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for configuration management. Settings can be configured via:

1. **Environment variables** with the `MEMORIOUS_` prefix (highest priority)
2. **`.env` file** in the working directory
3. **Docker secrets** in `/run/secrets` directory (lowest priority)

## Docker Secrets

Memorious supports [Docker secrets](https://docs.docker.com/engine/swarm/secrets/) for secure configuration of sensitive values like database URIs and API keys.

### How It Works

Docker secrets are mounted as files in `/run/secrets/`. Memorious reads these files automatically, using the filename (with `memorious_` prefix) as the setting name.

### Example: Database URI Secret

Create the secret:

```bash
# Using Docker Swarm
printf "postgresql://user:secret@db:5432/memorious" | docker secret create memorious_tags_uri -

# Or using Docker Compose with a file
echo "postgresql://user:secret@db:5432/memorious" > ./secrets/memorious_tags_uri
```

Docker Compose configuration:

```yaml
services:
  memorious:
    image: ghcr.io/dataresearchcenter/memorious:latest
    secrets:
      - memorious_tags_uri
    # No need to set MEMORIOUS_TAGS_URI in environment

secrets:
  memorious_tags_uri:
    file: ./secrets/memorious_tags_uri  # For file-based secrets
    # Or for Swarm secrets:
    # external: true
```

### Supported Secrets

Any Memorious setting can be provided as a Docker secret. Common use cases:

| Secret File | Setting |
|-------------|---------|
| `/run/secrets/memorious_tags_uri` | Database connection string |
| `/run/secrets/memorious_http_timeout` | HTTP timeout value |

### Priority

Environment variables take precedence over Docker secrets. This allows you to override secrets in specific deployments while keeping the base configuration secure.

## Environment Variables

### Core Configuration

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_APP_NAME` | `str` | `"memorious"` | Application name identifier |
| `MEMORIOUS_DEBUG` | `bool` | `false` | Enable debug mode with verbose logging and single-threaded execution |
| `MEMORIOUS_TESTING` | `bool` | `false` | Enable testing mode (uses FakeRedis instead of real Redis) |
| `MEMORIOUS_BASE_PATH` | `Path` | `./data` | Base directory for all data storage (archive, tags database, etc.) |
| `MEMORIOUS_CONFIG_PATH` | `Path` | `None` | Path to directory containing crawler YAML configuration files |

### Crawl Behavior

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_INCREMENTAL` | `bool` | `true` | Enable incremental crawling (skip previously crawled items within expiry window) |
| `MEMORIOUS_CONTINUE_ON_ERROR` | `bool` | `false` | Continue crawler execution when an error occurs instead of stopping |
| `MEMORIOUS_EXPIRE` | `int` | `1` | Number of days until cached/incremental crawl data expires |

### Rate Limiting

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_DB_RATE_LIMIT` | `int` | `6000` | Maximum database operations per minute |
| `MEMORIOUS_HTTP_RATE_LIMIT` | `int` | `120` | Maximum HTTP requests to a single host per minute |
| `MEMORIOUS_MAX_QUEUE_LENGTH` | `int` | `50000` | Maximum number of pending tasks in the queue before raising an error |

### HTTP Configuration

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_HTTP_CACHE` | `bool` | `true` | Enable HTTP response caching |
| `MEMORIOUS_HTTP_TIMEOUT` | `float` | `30.0` | HTTP request timeout in seconds |
| `MEMORIOUS_USER_AGENT` | `str` | `Mozilla/5.0 ... aleph.memorious/{VERSION}` | User-Agent header for HTTP requests |

### Tags Storage

Tags are used for incremental crawling state and HTTP response caching.

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_TAGS_URI` | `str` | `None` | Database URI for tags storage. Supports SQLite and PostgreSQL. Defaults to `sqlite:///{BASE_PATH}/tags.sqlite3` |
| `MEMORIOUS_TAGS_TABLE` | `str` | `"memorious_tags"` | Database table name for storing tags |

**Examples:**

```bash
# SQLite (default)
MEMORIOUS_TAGS_URI=sqlite:///./data/tags.sqlite3

# PostgreSQL
MEMORIOUS_TAGS_URI=postgresql://user:pass@localhost/memorious
```

## Servicelayer Settings

Memorious uses [servicelayer](https://github.com/alephdata/servicelayer) for file archiving and Redis connectivity. These are configured via separate environment variables (no `MEMORIOUS_` prefix):

### Archive Storage

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `ARCHIVE_TYPE` | `str` | `"file"` | Storage backend type: `file`, `s3`, or `gs` |
| `ARCHIVE_PATH` | `str` | `None` | Local directory for file storage (auto-set from `MEMORIOUS_BASE_PATH/archive` if not specified) |
| `ARCHIVE_BUCKET` | `str` | `None` | S3/GCS bucket name (required if `ARCHIVE_TYPE` is `s3` or `gs`) |
| `PUBLICATION_BUCKET` | `str` | `None` | Separate bucket for published/public files |

### AWS S3 (when `ARCHIVE_TYPE=s3`)

| Environment Variable | Description |
|---------------------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | AWS region (e.g., `us-east-1`) |

### Redis

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `REDIS_URL` | `str` | `None` | Redis connection URL. If not set, uses FakeRedis (single-threaded mode) |

**Examples:**

```bash
# Local Redis
REDIS_URL=redis://localhost:6379/0

# Redis with authentication
REDIS_URL=redis://:password@localhost:6379/0
```

## FTM Store Settings

When using the `ftm_store` operation to store FollowTheMoney entities, configure via [ftmq](https://github.com/investigativedata/ftmq) settings:

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `FTM_STORE_URI` | `str` | `sqlite:///ftm_fragments.db` | Database URI for FTM entity fragments storage |

## Aleph Integration

When using Aleph operations (`aleph_emit_document`, `aleph_emit_entity`), configure via [alephclient](https://github.com/alephdata/alephclient) settings:

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `ALEPH_HOST` | `str` | `https://data.occrp.org/` | Aleph instance URL |
| `ALEPH_API_KEY` | `str` | `None` | API key for Aleph authentication |

## Example Configuration

### Development (SQLite, no Redis)

```bash
export MEMORIOUS_DEBUG=true
export MEMORIOUS_BASE_PATH=./data
export MEMORIOUS_CONFIG_PATH=./config
```

### Production (PostgreSQL, Redis, S3)

```bash
# Core
export MEMORIOUS_BASE_PATH=/var/lib/memorious
export MEMORIOUS_CONFIG_PATH=/etc/memorious/config
export MEMORIOUS_DEBUG=false

# Tags database
export MEMORIOUS_TAGS_URI=postgresql://memorious:secret@db:5432/memorious

# Redis for task queue
export REDIS_URL=redis://redis:6379/0

# S3 for file storage
export ARCHIVE_TYPE=s3
export ARCHIVE_BUCKET=my-memorious-archive
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=eu-west-1

# FTM store
export FTM_STORE_URI=postgresql://memorious:secret@db:5432/memorious

# Aleph integration
export ALEPH_HOST=https://aleph.example.org/
export ALEPH_API_KEY=abc123...
```

### Docker Compose

```yaml
services:
  memorious:
    environment:
      MEMORIOUS_CONFIG_PATH: /config
      MEMORIOUS_BASE_PATH: /data
      MEMORIOUS_TAGS_URI: postgresql://user:pass@postgres/memorious
      REDIS_URL: redis://redis:6379/0
      FTM_STORE_URI: postgresql://user:pass@postgres/memorious
```

## Crawler-Level Overrides

Some settings can be overridden per-crawler in the YAML configuration:

```yaml
name: my_crawler
expire: 7  # Override MEMORIOUS_EXPIRE for this crawler
delay: 2   # Delay between tasks in seconds
stealthy: true  # Use random User-Agent
```

Stage-level parameters can also override global settings:

```yaml
pipeline:
  fetch:
    method: fetch
    params:
      http_rate_limit: 60  # Override for this stage only
      cache: false  # Disable HTTP caching for this stage
```
