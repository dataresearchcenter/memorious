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

> The solitary and lucid spectator of a multiform, instantaneous and almost intolerably precise world.
>
> -- [Funes the Memorious](http://users.clas.ufl.edu/burt/spaceshotsairheads/borges-funes.pdf),
> Jorge Luis Borges

`memorious` is a light-weight web scraping toolkit. It supports scrapers that
collect structured or un-structured data. This includes the following use cases:

* Make crawlers modular and simple tasks reusable
* Provide utility functions to do common tasks such as data storage, HTTP session management
* Integrate crawlers with the Aleph and FollowTheMoney ecosystem
* Get out of your way as much as possible

`memorious` is part of the [OpenAleph](https://openaleph.org) suite but can be used standalone as well.

## Design

When writing a scraper, you often need to paginate through through an index
page, then download an HTML page for each result and finally parse that page
and insert or update a record in a database.

`memorious` handles this by managing a set of `crawlers`, each of which
can be composed of multiple `stages`. Each `stage` is implemented using a
Python function, which can be reused across different `crawlers`.

The basic steps of writing a Memorious crawler:

1. Make YAML crawler configuration file
2. Add different stages
3. Write code for stage operations (optional)
4. Test, rinse, repeat

## Documentation

The documentation for Memorious is available at
[docs.investigraph.dev/lib/memorious](https://docs.investigraph.dev/lib/memorious).
Feel free to edit the source files in the `docs` folder and send pull requests for improvements.

To serve the documentation locally, run `mkdocs serve`

## License and Copyright


`memorious`, (C) -2024 Organized Crime and Corruption Reporting Project

`memorious`, (C) 2025 [Data and Research Center – DARC](https://dataresearchcenter.org)

`memorious4`, (C) 2026 [Data and Research Center – DARC](https://dataresearchcenter.org)

`memorious4` is licensed under the AGPLv3 or later license.

Prior to version 4.0.0, `memorious` was released under the MIT license.

see [NOTICE](./NOTICE) and [LICENSE](./LICENSE)
