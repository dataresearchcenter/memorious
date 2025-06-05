# Memorious

!!! info "About"
    Memorious is a light-weight web scraping toolkit. It supports scrapers that collect structured or un-structured data.

* Make crawlers modular and simple tasks reusable
* Provide utility functions to do common tasks such as data storage, HTTP session management
* Integrate crawlers with the Aleph and FollowTheMoney ecosystem
* Get out of your way as much as possible

## Design

When writing a scraper, you often need to paginate through through an index page, then download an HTML page for each result and finally parse that page and insert or update a record in a database.

Memorious handles this by managing a set of ``crawlers``, each of which  can be composed of multiple ``stages``. Each ``stage`` is implemented using a Python function, which can be reused across different ``crawlers``.

The basic steps of writing a Memorious crawler:

1. Make YAML crawler configuration file
2. Add different stages
3. Write code for stage operations (optional)
4. Test, rinse, repeat

## Documentation

<div class="grid cards" markdown>

- [Install Memorious and run your own crawlers](./installation.md)
- [Reference for the command-line tool to run and monitor crawlers](./cli.md)
- [Build your own crawler using YAML configuration](./reference.md)
- [Links to our Git repository and licensing information](./development.md)

</div>
