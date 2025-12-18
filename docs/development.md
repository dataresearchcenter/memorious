# Development

## Repository

[https://github.com/dataresearchcenter/memorious](https://github.com/dataresearchcenter/memorious)

## Setup

```bash
git clone https://github.com/dataresearchcenter/memorious.git
cd memorious
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Fork History

This is a hard fork of the [original memorious project](https://github.com/alephdata/memorious) that was discontinued in 2023.

### Changelog since v2.6.4

- Remove OCR feature
- Remove dataset (db operations)
- Replace Redis with procrastinate job queue
- Replace servicelayer with anystore/ftm-lakehouse
- Use httpx instead of requests
- Operations registry (replaces entry points)

## License

[MIT License](https://github.com/dataresearchcenter/memorious/blob/master/LICENSE)
