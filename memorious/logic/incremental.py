"""Advanced incremental crawling with target-based skipping.

This module provides utilities for advanced incremental crawling where
stages can be skipped based on whether a target stage (like "store")
has already been completed for a given identifier.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from anystore.util import join_relpaths as make_key
from banal import ensure_dict, ensure_list

from memorious.helpers.xpath import extract_xpath

if TYPE_CHECKING:
    from memorious.logic.context import Context


def should_skip_incremental(
    context: Context,
    data: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> bool:
    """Check if stage should be skipped based on target completion.

    This enables advanced incremental crawling where earlier stages are
    skipped if the target stage (e.g., "store") has already completed
    for the same identifier.

    Args:
        context: The crawler context.
        data: Current stage data (may be modified to add skip_incremental info).
        config: Optional override config, otherwise uses context.params.

    Returns:
        True if the stage should be skipped, False otherwise.

    Example YAML configuration::

        pipeline:
          fetch:
            method: fetch
            params:
              skip_incremental:
                key:
                  data: [document_id, url]  # Try these keys as identifier
                  urlpattern: "https://example.com/doc/.*"  # Or match URL
                  xpath: './/meta[@name="id"]/@content'  # Or extract from HTML
                target: store  # Skip if "store" stage completed for this ID
            handle:
              pass: parse
    """
    settings = context.settings
    if not settings.incremental:
        return False

    config = config or context.params.get("skip_incremental")
    if not config:
        return False

    config = ensure_dict(config)
    key_config = ensure_dict(config.get("key"))
    identifier = None

    # Try data keys
    for key in ensure_list(key_config.get("data")):
        if key in data:
            identifier = data[key]
            break

    # Try URL pattern
    if identifier is None and key_config.get("urlpattern"):
        url = data.get("url", "")
        if re.match(key_config["urlpattern"], url):
            identifier = url

    # Try XPath extraction from cached response
    if identifier is None and key_config.get("xpath"):
        result = context.http.rehash(data)
        if hasattr(result, "html") and result.html is not None:
            identifier = extract_xpath(result.html, key_config["xpath"])

    # Default to URL
    identifier = identifier or data.get("url")

    if identifier:
        target = config.get("target", "store")
        target_key = make_key("skip_incremental", str(identifier), target)
        data["skip_incremental"] = {"target": target, "key": target_key}

        if context.check_tag(target_key):
            context.log.info("Skipping (incremental)", key=target_key)
            return True

    return False


def mark_incremental_complete(context: Context, data: dict[str, Any]) -> None:
    """Mark incremental target as complete.

    Should be called when a target stage (like "store") completes successfully.
    This sets a tag that will cause future runs to skip earlier stages for
    the same identifier.

    Args:
        context: The crawler context.
        data: Stage data containing skip_incremental info.

    Example:
        Called automatically by the `store` operation when configured with
        incremental support.
    """
    incremental = ensure_dict(data.get("skip_incremental"))
    if incremental.get("target") == context.stage.name:
        key = incremental.get("key")
        if key:
            context.set_tag(key, True)
            context.log.debug("Marked incremental complete", key=key)
