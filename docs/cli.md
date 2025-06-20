# CLI Reference

!!! info "About this section"
    Memorious is controlled via a command-line tool, which can be used to monitor or invoke a crawler interactively.

See the status of all crawlers managed by memorious:

```sh
memorious list
```

Run a specific crawler:

```sh
memorious run my_crawler
```

Run a specific crawler with a multi-threaded worker

```sh
memorious run my_crawler --threads=4
```

Clear all the run status and cached information associated with a crawler:

```sh
memorious flush my_crawler
```

Clear only the cached information associated with a crawler:

```sh
memorious flush_tags my_crawler
```
