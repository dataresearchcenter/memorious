"""Initializer operations for starting crawler pipelines.

This module provides operations that serve as entry points for crawlers,
generating initial data items such as seed URLs, sequences, and dates.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from banal import ensure_dict, ensure_list
from dateutil.relativedelta import relativedelta

from memorious.operations import register

if TYPE_CHECKING:
    from memorious.logic.context import Context


@register("init")
def init(context: Context, data: dict[str, Any]) -> None:
    """Initialize crawler with params and optional proxy configuration.

    Merges stage params into the data dict and configures HTTP proxy
    if MEMORIOUS_HTTP_PROXY is set and not in debug mode.

    Args:
        context: The crawler context.
        data: Initial data dict.

    Params:
        Any params are merged into the emitted data.

    Example:
        ```yaml
        pipeline:
          init:
            method: init
            params:
              api_key: ${API_KEY}
              base_url: https://api.example.com
            handle:
              pass: fetch
        ```
    """
    # Configure proxy if set
    proxy = context.settings.http_proxy
    if proxy and not context.settings.debug:
        context.http.client._mounts.clear()
        import httpx

        context.http.client._mounts[httpx.URL("http://")] = httpx.HTTPTransport(
            proxy=proxy
        )
        context.http.client._mounts[httpx.URL("https://")] = httpx.HTTPTransport(
            proxy=proxy
        )
        context.http.save()
        context.log.info("Configured HTTP proxy", proxy=proxy)

    # Merge params into data
    context.emit(data={**data, **ensure_dict(context.params)})


@register("seed")
def seed(context: Context, data: dict[str, Any]) -> None:
    """Initialize a crawler with seed URLs.

    Emits data items for each URL provided in the configuration.
    URLs can contain format placeholders that are substituted with
    values from the incoming data dict.

    Args:
        context: The crawler context.
        data: Values available for URL formatting.

    Params:
        url: Single URL or list of URLs.
        urls: List of URLs (alternative to `url`).

    Example:
        ```yaml
        pipeline:
          init:
            method: seed
            params:
              urls:
                - https://example.com/page/1
                - https://example.com/page/2
            handle:
              pass: fetch

          # Or with dynamic URLs:
          seed_dynamic:
            method: seed
            params:
              url: "https://example.com/items/%(item_id)s"
            handle:
              pass: fetch
        ```
    """
    for key in ("url", "urls"):
        for url in ensure_list(context.params.get(key)):
            url = url % data
            context.emit(data={"url": url})


@register("enumerate")
def enumerate(context: Context, data: dict[str, Any]) -> None:
    """Iterate through a set of items and emit each one.

    Takes a list of items from configuration and emits a data item
    for each, with the item value available as `data["item"]`.

    Args:
        context: The crawler context.
        data: Base data dict to include in each emission.

    Params:
        items: List of items to enumerate.

    Example:
        ```yaml
        pipeline:
          init:
            method: enumerate
            params:
              items:
                - category_a
                - category_b
                - category_c
            handle:
              pass: seed

          seed:
            method: seed
            params:
              url: "https://example.com/%(item)s"
            handle:
              pass: fetch
        ```
    """
    items = ensure_list(context.params.get("items"))
    for item in items:
        data["item"] = item
        context.emit(data=data)


@register("tee")
def tee(context: Context, data: dict[str, Any]) -> None:
    """Trigger multiple subsequent stages in parallel.

    Emits to all configured handlers, useful for splitting a pipeline
    into multiple parallel branches.

    Args:
        context: The crawler context.
        data: Data to pass to all branches.

    Example:
        ```yaml
        pipeline:
          fetch:
            method: fetch
            handle:
              pass: tee

          tee:
            method: tee
            handle:
              pdf: store_pdf
              metadata: extract_meta
              archive: backup

          store_pdf:
            method: directory
            # ...
        ```
    """
    for rule, _ in context.stage.handlers.items():
        context.emit(rule=rule, data=data)


@register("sequence")
def sequence(context: Context, data: dict[str, Any]) -> None:
    """Generate a sequence of numbers.

    The memorious equivalent of Python's range(), accepting start,
    stop, and step parameters. Supports two modes:
    - Immediate: generates all numbers in the range at once.
    - Recursive: generates numbers one by one with optional delay.

    The recursive mode is useful for very large sequences to avoid
    overwhelming the job queue.

    Args:
        context: The crawler context.
        data: May contain "number" to continue a recursive sequence.

    Params:
        start: Starting number (default: 1).
        stop: Stop number (exclusive).
        step: Step increment (default: 1, can be negative).
        delay: If set, use recursive mode with this delay in seconds.
        tag: If set, emit each number only once across crawler runs.

    Example:
        ```yaml
        pipeline:
          pages:
            method: sequence
            params:
              start: 1
              stop: 100
              step: 1
            handle:
              pass: fetch

          # Recursive mode for large sequences:
          large_sequence:
            method: sequence
            params:
              start: 1
              stop: 10000
              delay: 5  # 5 second delay between emissions
              tag: page_sequence  # Incremental: skip already processed
            handle:
              pass: fetch
        ```
    """
    number = data.get("number", context.params.get("start", 1))
    stop = context.params.get("stop")
    step = context.params.get("step", 1)
    delay = context.params.get("delay")
    prefix = context.params.get("tag")
    while True:
        tag = None if prefix is None else "%s:%s" % (prefix, number)

        if tag is None or not context.check_tag(tag):
            data["number"] = number
            context.emit(data=data)

        if tag is not None:
            context.set_tag(tag, True)

        number = number + step
        if step > 0 and number >= stop:
            break
        if step < 0 and number <= stop:
            break

        if delay is not None:
            data["number"] = number
            context.recurse(data=data, delay=delay)
            break


@register("dates")
def dates(context: Context, data: dict[str, Any]) -> None:
    """Generate a sequence of dates.

    Generates dates by iterating between begin and end dates with a specified
    interval. Direction is determined automatically: if begin > end, iterates
    backwards; if begin < end, iterates forwards. Useful for scraping
    date-based archives.

    Args:
        context: The crawler context.
        data: Base data dict to include in each emission.

    Params:
        format: Date format string (default: "%Y-%m-%d").
        begin: Begin date string (default: current date).
        end: End date string (default: current date).
        days: Number of days per step (default: 0).
        weeks: Number of weeks per step (default: 0).
        months: Number of months per step (default: 0).
        years: Number of years per step (default: 0).

    Example:
        ```yaml
        pipeline:
          # Iterate backwards from now to 2020:
          monthly_backwards:
            method: dates
            params:
              end: "2020-01-01"
              months: 1
            handle:
              pass: fetch

          # Iterate forwards from 2020 to 2024:
          daily_forwards:
            method: dates
            params:
              begin: "2020-01-01"
              end: "2024-01-01"
              days: 1
            handle:
              pass: fetch

          # Just today (both default to now):
          today_only:
            method: dates
            params:
              days: 1
            handle:
              pass: fetch
        ```

    Note:
        Each emission includes both `date` (formatted string) and
        `date_iso` (ISO format) for flexibility. The original data
        dict is preserved in each emission.
    """
    format_ = context.params.get("format", "%Y-%m-%d")

    days = context.params.get("days", 0)
    weeks = context.params.get("weeks", 0)
    months = context.params.get("months", 0)
    years = context.params.get("years", 0)

    if not any([days, weeks, months, years]):
        context.log.error("No interval given", params=context.params)
        return

    delta = relativedelta(days=days, weeks=weeks, months=months, years=years)

    now = datetime.now()

    if "begin" in context.params:
        begin = datetime.strptime(context.params["begin"], format_)
    else:
        begin = now

    if "end" in context.params:
        end = datetime.strptime(context.params["end"], format_)
    else:
        end = now

    # Determine direction based on begin/end relationship
    if begin >= end:
        # Iterate backwards
        current = begin
        while current >= end:
            context.emit(
                data={
                    **data,
                    "date": current.strftime(format_),
                    "date_iso": current.isoformat(),
                }
            )
            current = current - delta
    else:
        # Iterate forwards
        current = begin
        while current <= end:
            context.emit(
                data={
                    **data,
                    "date": current.strftime(format_),
                    "date_iso": current.isoformat(),
                }
            )
            current = current + delta
