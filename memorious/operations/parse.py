"""HTML, XML, JSON, and CSV parsing operations.

This module provides operations for parsing various content types,
extracting metadata, and handling pagination in web crawlers.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urljoin

import jq
from anystore.logging import get_logger
from banal import clean_dict, ensure_dict, ensure_list
from normality import collapse_spaces

from memorious.helpers.dates import iso_date
from memorious.helpers.pagination import paginate
from memorious.helpers.rule import parse_rule
from memorious.operations import register
from memorious.util import make_url_key

if TYPE_CHECKING:
    from lxml.html import HtmlElement

    from memorious.logic.context import Context

log = get_logger(__name__)

URL_TAGS = [
    (".", "href"),
    (".//a", "href"),
    (".//img", "src"),
    (".//link", "href"),
    (".//iframe", "src"),
]


def _extract_urls(
    context: Context,
    data: dict[str, Any],
    html: HtmlElement,
    base_url: str,
) -> None:
    """Extract URLs from HTML and emit them for fetching.

    Args:
        context: The crawler context.
        data: Current stage data.
        html: HTML element to extract URLs from.
        base_url: Base URL for resolving relative links.
    """
    include = context.params.get("include_paths")
    if include is None:
        roots = [html]
    else:
        roots = []
        for path in include:
            roots = roots + html.xpath(path)

    seen = set()
    for root in roots:
        for tag_query, attr_name in URL_TAGS:
            for element in root.xpath(tag_query):
                attr = element.get(attr_name)
                if attr is None:
                    continue

                try:
                    url = urljoin(base_url, attr)
                except Exception:
                    log.warning("Invalid URL", url=attr)
                    continue

                if url is None or url in seen:
                    continue
                seen.add(url)

                tag = context.make_key(context.run_id, make_url_key(url))
                if context.check_tag(tag):
                    continue
                context.set_tag(tag, None)

                emit_data = {**data, "url": url}

                if emit_data.get("title") is None:
                    if context.get("link_title", False):
                        emit_data["title"] = collapse_spaces(element.text_content())
                    elif element.get("title"):
                        emit_data["title"] = collapse_spaces(element.get("title"))

                # Encode non-ASCII characters for HTTP header
                context.http.client.headers["Referer"] = quote(
                    url, safe=":/?#[]@!$&'()*+,;="
                )
                context.emit(rule="fetch", data=emit_data)


def _extract_metadata(
    context: Context, data: dict[str, Any], html: HtmlElement
) -> dict[str, Any]:
    """Extract metadata from HTML/XML using XPath expressions.

    Args:
        context: The crawler context.
        data: Data dict to update with extracted metadata.
        html: HTML/XML element to extract from.

    Returns:
        Updated data dict.
    """
    meta = context.params.get("meta", {})
    meta_date = context.params.get("meta_date", {})

    meta_paths = {**meta, **meta_date}

    for key, xpaths in meta_paths.items():
        for xpath in ensure_list(xpaths):
            for element in ensure_list(html.xpath(xpath)):
                try:
                    value = collapse_spaces(element.text_content())
                except AttributeError:
                    value = collapse_spaces(str(element))
                if key in meta_date:
                    value = iso_date(value)
                if value is not None:
                    data[key] = value
                break
    return data


def _extract_ftm(context: Context, data: dict[str, Any], html: HtmlElement) -> None:
    """Extract FollowTheMoney entity properties from HTML.

    Args:
        context: The crawler context.
        data: Data dict to update with FTM properties.
        html: HTML element to extract from.
    """
    properties = context.params.get("properties")
    properties_dict = {}
    for key, value in properties.items():
        properties_dict[key] = html.xpath(value)

    data["schema"] = context.params.get("schema")
    data["properties"] = properties_dict


@register("parse")
def parse(context: Context, data: dict[str, Any]) -> None:
    """Parse HTML response and extract URLs and metadata.

    The main parsing operation that extracts URLs from HTML documents
    for further crawling and metadata based on XPath expressions.

    Args:
        context: The crawler context.
        data: Must contain cached HTTP response data.

    Params:
        include_paths: List of XPath expressions to search for URLs.
        meta: Dict mapping field names to XPath expressions.
        meta_date: Dict mapping date field names to XPath expressions.
        store: Rules dict to match responses for storage.
        schema: FTM schema name for entity extraction.
        properties: Dict mapping FTM properties to XPath expressions.

    Example:
        ```yaml
        pipeline:
          parse:
            method: parse
            params:
              include_paths:
                - './/div[@class="content"]//a'
              meta:
                title: './/h1/text()'
                author: './/span[@class="author"]/text()'
              meta_date:
                published_at: './/time/@datetime'
              store:
                mime_group: documents
            handle:
              fetch: fetch
              store: store
        ```
    """
    with context.http.rehash(data) as result:
        if result.html is not None:
            context.log.info("Parse HTML", url=result.url)

            # Extract page title
            for title in result.html.xpath(".//title/text()"):
                if title is not None and "title" not in data:
                    data["title"] = title

            _extract_metadata(context, data, result.html)

            if context.params.get("schema") is not None:
                _extract_ftm(context, data, result.html)

            _extract_urls(context, data, result.html, result.url)

        rules = context.params.get("store") or {"match_all": {}}
        if parse_rule(rules).apply(result):
            context.emit(rule="store", data=data)


@register("parse_listing")
def parse_listing(context: Context, data: dict[str, Any]) -> None:
    """Parse HTML listing with multiple items.

    Extracts metadata from a list of items on a page and handles
    pagination. Useful for search results, archives, and index pages.

    Args:
        context: The crawler context.
        data: Must contain cached HTTP response data.

    Params:
        items: XPath expression to select item elements.
        meta: Dict mapping field names to XPath expressions (per item).
        pagination: Pagination configuration.
        emit: If True, emit each item's data.
        parse_html: If True, extract URLs from items (default: True).

    Example:
        ```yaml
        pipeline:
          parse_results:
            method: parse_listing
            params:
              items: './/div[@class="result-item"]'
              meta:
                title: './/h2/text()'
                url: './/a/@href'
              pagination:
                total_pages: './/span[@class="pages"]/text()'
                param: page
              emit: true
            handle:
              item: fetch_detail
              next_page: fetch
        ```
    """
    should_emit = context.params.get("emit") is True
    should_parse_html = context.params.get("parse_html", True) is True
    items_xpath = context.params.get("items")

    with context.http.rehash(data) as result:
        if result.html is not None:
            base_url = data.get("url", result.url)

            for item in result.html.xpath(items_xpath):
                item_data = {**data}
                _extract_metadata(context, item_data, item)

                if should_parse_html:
                    _extract_urls(context, item_data, item, base_url)
                if should_emit:
                    context.emit(rule="item", data=item_data)

            paginate(context, data, result.html)

            rules = context.params.get("store") or {"match_all": {}}
            if parse_rule(rules).apply(result):
                context.emit(rule="store", data=data)


@register("parse_jq")
def parse_jq(context: Context, data: dict[str, Any]) -> None:
    """Parse JSON response using jq patterns.

    Uses the jq query language to extract data from JSON responses.
    Emits one data item for each result from the jq query.

    Args:
        context: The crawler context.
        data: Must contain cached HTTP response data.

    Params:
        pattern: jq pattern string to extract data.

    Example:
        ```yaml
        pipeline:
          parse_api:
            method: parse_jq
            params:
              pattern: '.results[] | {id: .id, name: .title, url: .links.self}'
            handle:
              pass: fetch_detail
        ```
    """
    result = context.http.rehash(data)
    json_data = clean_dict(result.json)

    pattern = context.params["pattern"]
    jq_result = jq.compile(pattern).input(json_data)
    for item in jq_result.all():
        context.emit(data={**data, **item})


@register("parse_csv")
def parse_csv(context: Context, data: dict[str, Any]) -> None:
    """Parse CSV file and emit rows.

    Reads a CSV file and emits each row as a data item. Can also
    emit all rows together as a list.

    Args:
        context: The crawler context.
        data: Must contain cached HTTP response data.

    Params:
        skiprows: Number of rows to skip at the beginning.
        delimiter: CSV field delimiter (default: comma).
        (Other csv.DictReader kwargs are supported)

    Example:
        ```yaml
        pipeline:
          parse_data:
            method: parse_csv
            params:
              skiprows: 1
              delimiter: ";"
            handle:
              row: process_row
              rows: store_all
        ```
    """
    result = context.http.rehash(data)
    parserkwargs = ensure_dict(context.params)
    skiprows = parserkwargs.pop("skiprows", 0)

    with result.local_path() as local_path:
        with open(local_path, encoding="utf-8") as fh:
            reader = csv.DictReader(fh, **parserkwargs)
            for _ in range(skiprows):
                next(reader, None)
            rows = []
            for row in reader:
                context.emit(rule="row", data=row, optional=True)
                rows.append(row)
            context.emit(rule="rows", data={**data, "rows": rows})


@register("parse_xml")
def parse_xml(context: Context, data: dict[str, Any]) -> None:
    """Parse XML response and extract metadata.

    Parses an XML document and extracts metadata using XPath expressions.

    Args:
        context: The crawler context.
        data: Must contain cached HTTP response data.

    Params:
        meta: Dict mapping field names to XPath expressions.
        meta_date: Dict mapping date field names to XPath expressions.

    Example:
        ```yaml
        pipeline:
          parse_feed:
            method: parse_xml
            params:
              meta:
                title: './/item/title/text()'
                link: './/item/link/text()'
            handle:
              pass: fetch
        ```
    """
    result = context.http.rehash(data)
    if result.xml is not None:
        _extract_metadata(context, data, result.xml)
    context.emit(data=data)
