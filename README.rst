=========
Memorious
=========

    The solitary and lucid spectator of a multiform, instantaneous and almost intolerably precise world.

    -- `Funes the Memorious <http://users.clas.ufl.edu/burt/spaceshotsairheads/borges-funes.pdf>`_,
    Jorge Luis Borges

.. image:: https://github.com/alephdata/memorious/workflows/memorious/badge.svg

``memorious`` is a light-weight web scraping toolkit. It supports scrapers that
collect structured or un-structured data. This includes the following use cases:

* Make crawlers modular and simple tasks reusable
* Provide utility functions to do common tasks such as data storage, HTTP session management
* Integrate crawlers with the Aleph and FollowTheMoney ecosystem
* Get out of your way as much as possible

Design
------

When writing a scraper, you often need to paginate through through an index
page, then download an HTML page for each result and finally parse that page
and insert or update a record in a database.

``memorious`` handles this by managing a set of ``crawlers``, each of which
can be composed of multiple ``stages``. Each ``stage`` is implemented using a
Python function, which can be reused across different ``crawlers``.

The basic steps of writing a Memorious crawler:

1. Make YAML crawler configuration file
2. Add different stages
3. Write code for stage operations (optional)
4. Test, rinse, repeat

Documentation
-------------

The documentation for Memorious is available at
`docs.investigraph.dev/lib/memorious <https://docs.investigraph.dev/lib/memorious>`_.
Feel free to edit the source files in the ``docs`` folder and send pull requests for improvements.

To serve the documentation locally, run ``mkdocs serve``
