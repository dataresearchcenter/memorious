# Installation

!!! info "About this section"
    This page explains how you can install Memorious to run your own crawlers.

We recommend using [Docker Compose](https://docs.docker.com/compose/) to run your crawlers in production, and we have an [example project](https://github.com/alephdata/memorious/tree/master/example) to help you get started.

- Make a copy of the `memorious/example` directory.
- Add your own crawler YAML configurations into the `config` directory.
- Add your Python extensions into the `src` directory (if applicable).
- Update `setup.py` with the name of your project and any additional dependencies.
- If you need to (eg. if your database connection or directory structure is different), update any environment variables in the `Dockerfile` or `docker-compose.yml`, although the defaults should work fine.
- Run `docker-compose up -d`. This might take a while when it's building for the first time.

## Run a crawler

- You can access the Memorious CLI through the `shell` container:

```
docker-compose run --rm shell
```

To see the crawlers available to you:

```
memorious list
```

And to run a crawler:

```
memorious run my_crawler
```

See [Usage](https://memorious.readthedocs.io/en/latest/usage.html) (or run `memorious --help`) for the complete list of Memorious commands.

<Callout>
  You can use any directory structure you like, `src` and `config` are not required, and nor is separation of YAML and Python files. So long as the `MEMORIOUS_CONFIG_PATH` environment variable points to a directory containing, within any level of directory nesting, your YAML files, Memorious will find them.
</Callout>

## Environment variables

Your Memorious instance is configured by environment variables that control database connectivity and general principles of how the system operates. You can set all of these in the `Dockerfile`.

For a complete list of all available settings, see the [Settings Reference](reference/settings.md).

### Quick Reference

**Core Settings:**

- `MEMORIOUS_CONFIG_PATH`: path to crawler pipeline YAML configurations
- `MEMORIOUS_BASE_PATH`: base directory for data storage (default: `./data`)
- `MEMORIOUS_DEBUG`: enable debug mode with single-threaded execution (default: `false`)
- `MEMORIOUS_INCREMENTAL`: enable incremental crawling (default: `true`)
- `MEMORIOUS_EXPIRE`: days until cached data expires (default: `1`)

**HTTP Settings:**

- `MEMORIOUS_HTTP_RATE_LIMIT`: max HTTP requests per host per minute (default: `120`)
- `MEMORIOUS_HTTP_CACHE`: enable HTTP response caching (default: `true`)
- `MEMORIOUS_USER_AGENT`: custom User-Agent string

**Storage Settings:**

- `MEMORIOUS_TAGS_URI`: database URI for tags/caching (default: SQLite in `BASE_PATH`)
- `REDIS_URL`: Redis connection URL (uses FakeRedis if not set)
- `ARCHIVE_TYPE`: storage backend - `file`, `s3`, or `gs` (default: `file`)
- `ARCHIVE_PATH`: local directory for file storage
- `ARCHIVE_BUCKET`: S3/GCS bucket name

**Integrations:**

- `FTM_STORE_URI`: database URI for FTM entity storage
- `ALEPH_HOST`: Aleph instance URL (default: `https://data.occrp.org/`)
- `ALEPH_API_KEY`: API key for Aleph authentication

## Shut it down

To gracefully exit, run `docker-compose down`.

Files which were downloaded by crawlers you ran, Memorious progress data from the Redis database, and the Redis task queue, are all persisted in the `build` directory, and will be reused next time you start it up. (If you need a completely fresh start, you can delete this directory).

## Building a crawler

To understand what goes into your `config` and `src` directories, check out the [examples](https://github.com/alephdata/memorious/tree/master/example) and [reference documentation](https://memorious.readthedocs.io/en/latest/buildingcrawler.html).

### Crawler Development mode

When you're working on your crawlers, it's not convenient to rebuild your Docker containers all the time. To run without Docker:

- Copy the environment variables from the `env.sh.tmpl` to `env.sh`. Make sure `MEMORIOUS_CONFIG_PATH` points to your crawler YAML files, wherever they may be.
- Run `source env.sh`.
- Run `pip install memorious`. If your crawlers use Python extensions, you'll need to run `pip install` in your crawlers directory as well
- Run `memorious list` to list your crawlers and `memorious run your-crawler` to run a crawler.

_Note: In development mode Memorious uses a single threaded worker (because FakeRedis is single threaded). So task execution concurrency is limited and the worker executes stages in a crawler's pipeline linearly one after another._
