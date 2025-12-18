# Settings Reference

Memorious uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for configuration management. Settings can be configured via:

1. **Environment variables** with the `MEMORIOUS_` prefix (highest priority)
2. **`.env` file** in the working directory
3. **Docker secrets** in `/run/secrets` directory (lowest priority)

## Docker Secrets

Memorious supports [Docker secrets](https://docs.docker.com/engine/swarm/secrets/) for secure configuration of sensitive values like database URIs and API keys.

### How It Works

Docker secrets are mounted as files in `/run/secrets/`. Memorious reads these files automatically, using the filename (with `memorious_` prefix) as the setting name.

### Example: Tags URI Secret

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

### Priority

Environment variables take precedence over Docker secrets. This allows you to override secrets in specific deployments while keeping the base configuration secure.

## Environment Variables

### Core Configuration

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_DEBUG` | `bool` | `false` | Enable debug mode with verbose logging |
| `MEMORIOUS_TESTING` | `bool` | `false` | Enable testing mode |
| `MEMORIOUS_BASE_PATH` | `Path` | `./data` | Base directory for all data storage |

### Crawl Behavior

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_INCREMENTAL` | `bool` | `true` | Enable incremental crawling (skip previously crawled items within expiry window) |
| `MEMORIOUS_CONTINUE_ON_ERROR` | `bool` | `false` | Continue crawler execution when an error occurs instead of stopping |
| `MEMORIOUS_EXPIRE` | `int` | `1` | Number of days until incremental crawl data expires |

### Rate Limiting

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_HTTP_RATE_LIMIT` | `int` | `120` | Maximum HTTP requests to a single host per minute |

### HTTP Configuration

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_HTTP_CACHE` | `bool` | `true` | Enable HTTP response caching |
| `MEMORIOUS_HTTP_TIMEOUT` | `float` | `30.0` | HTTP request timeout in seconds |
| `MEMORIOUS_USER_AGENT` | `str` | `Mozilla/5.0 ... memorious/{VERSION}` | User-Agent header for HTTP requests |

### Storage Configuration

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `MEMORIOUS_CACHE_URI` | `str` | `memory://` | URI for runtime cache (HTTP sessions). Supports `memory://`, `redis://`, file paths |
| `MEMORIOUS_TAGS_URI` | `str` | `None` | URI for tags storage (incremental state). Defaults to archive-based storage |

**Examples:**

```bash
# In-memory cache (default, good for single-process)
MEMORIOUS_CACHE_URI=memory://

# Redis cache (required for multi-worker deployments)
MEMORIOUS_CACHE_URI=redis://localhost:6379/0

# SQLite tags
MEMORIOUS_TAGS_URI=sqlite:///./data/tags.sqlite3

# PostgreSQL tags
MEMORIOUS_TAGS_URI=postgresql://user:pass@localhost/memorious
```

## Job Queue (Procrastinate)

Memorious uses [openaleph-procrastinate](https://github.com/openaleph/openaleph-procrastinate) for job queue management. Configure via these environment variables (no `MEMORIOUS_` prefix):

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `PROCRASTINATE_DB_URI` | `str` | `memory:` | Database URI for job queue. Use `memory:` for testing, PostgreSQL for production |
| `PROCRASTINATE_SYNC` | `bool` | `false` | Enable synchronous execution (useful for testing) |

**Examples:**

```bash
# In-memory (testing only)
PROCRASTINATE_DB_URI=memory:
PROCRASTINATE_SYNC=1

# PostgreSQL (production)
PROCRASTINATE_DB_URI=postgresql://user:pass@localhost/memorious
```

## Archive Storage (ftm-lakehouse)

File storage is handled by [ftm-lakehouse](https://github.com/openaleph/ftm-lakehouse). Configure via:

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `LAKEHOUSE_URI` | `str` | `data` | Base URI for archive storage. Can be local path or cloud storage URI |

**Examples:**

```bash
# Local storage
LAKEHOUSE_URI=./data

# S3 storage
LAKEHOUSE_URI=s3://my-bucket/memorious
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

### Development (In-Memory, Single Process)

```bash
export MEMORIOUS_DEBUG=true
export MEMORIOUS_BASE_PATH=./data

# Use in-memory for everything (default)
export MEMORIOUS_CACHE_URI=memory://
export PROCRASTINATE_DB_URI=memory:
export PROCRASTINATE_SYNC=1
```

### Production (PostgreSQL, Redis)

```bash
# Core
export MEMORIOUS_BASE_PATH=/var/lib/memorious
export MEMORIOUS_DEBUG=false

# Runtime cache (Redis for multi-worker)
export MEMORIOUS_CACHE_URI=redis://redis:6379/0

# Tags storage
export MEMORIOUS_TAGS_URI=postgresql://memorious:secret@db:5432/memorious

# Job queue
export PROCRASTINATE_DB_URI=postgresql://memorious:secret@db:5432/memorious

# Archive storage
export LAKEHOUSE_URI=s3://my-bucket/memorious

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
    image: ghcr.io/dataresearchcenter/memorious:latest
    environment:
      MEMORIOUS_BASE_PATH: /data
      MEMORIOUS_CACHE_URI: redis://redis:6379/0
      MEMORIOUS_TAGS_URI: postgresql://user:pass@postgres/memorious
      PROCRASTINATE_DB_URI: postgresql://user:pass@postgres/memorious
      LAKEHOUSE_URI: /data/archive
      FTM_STORE_URI: postgresql://user:pass@postgres/memorious
    volumes:
      - ./data:/data
    depends_on:
      - postgres
      - redis

  worker:
    image: ghcr.io/dataresearchcenter/memorious:latest
    command: memorious worker --concurrency 4
    environment:
      MEMORIOUS_CACHE_URI: redis://redis:6379/0
      MEMORIOUS_TAGS_URI: postgresql://user:pass@postgres/memorious
      PROCRASTINATE_DB_URI: postgresql://user:pass@postgres/memorious
      LAKEHOUSE_URI: /data/archive
    volumes:
      - ./data:/data
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: memorious
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7

volumes:
  postgres_data:
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
