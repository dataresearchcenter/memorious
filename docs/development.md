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

### Changelog since v2.6.4 (last legacy release)

- Remove OCR feature
- Remove dataset (db operations)
- Replace Redis workers / queue with [procrastinate job queue](https://openaleph.org/docs/lib/openaleph-procrastinate/)
- Replace `servicelayer` with [ftm-lakehouse](https://openaleph.org/docs/lib/ftm-lakehouse/) for storage
- Use [httpx](https://www.python-httpx.org/) instead of `requests`
- Operations registry (replaces entry points)
- Many more useful [operations and helpers](./operations.md)

## License

[MIT License](https://github.com/dataresearchcenter/memorious/blob/master/LICENSE)
