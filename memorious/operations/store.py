"""File storage operations.

This module provides operations for storing crawled files to various
backends including local directories and ftm-lakehouse archives.
"""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

from anystore.util import join_relpaths, make_checksum
from normality import safe_filename
from rigour.mime import normalize_mimetype

from memorious.helpers.template import render_template
from memorious.operations import register

if TYPE_CHECKING:
    from memorious.logic.context import Context


CRAWL_ORIGIN = "crawl"


def _get_directory_path(context: Context) -> str:
    """Get the base storage path for directory storage."""
    path = os.path.join(context.settings.base_path, "store")
    path = context.params.get("path", path)
    path = os.path.join(path, context.crawler.name)
    path = os.path.abspath(os.path.expandvars(path))
    try:
        os.makedirs(path)
    except Exception:
        pass
    return path


def _compute_file_path(
    context: Context,
    data: dict[str, Any],
    content_hash: str,
    raw_file_name: str | None = None,
    safe_names: bool = True,
) -> Path:
    """Compute the target file path based on compute_path configuration.

    Extracts file name and MIME type from data dict if not provided, then computes
    the relative path using the configured method.

    Supports multiple methods for computing file paths:
    - url_path (default): Use the URL path (with optional domain prefix and strip_prefix)
    - template: Use a Jinja2 template with data context
    - file_name: Use only the file name

    Args:
        context: The crawler context with params.
        data: The data dictionary (available in templates). Should contain:
            - headers: dict with Content-Type for MIME type detection
            - file_name: optional file name override
            - url: required for url_path method
        content_hash: The content hash of the file.
        raw_file_name: Optional file name override (e.g., from HTTP response).

    Returns:
        A Path object representing the relative file path. Use str(path) for the
        complete relative path and path.name for just the file name.

    Raises:
        ValueError: If the path cannot be computed (e.g., missing template, no URL,
            no filename in URL path, unknown method).

    Example YAML configs:
        ```yaml
        # Default behavior uses url_path (no config needed)

        # Use URL path with domain prefix
        params:
          compute_path:
            method: url_path
            params:
              include_domain: true

        # Use URL path with prefix stripped
        params:
          compute_path:
            method: url_path
            params:
              strip_prefix: "/api/v1/documents"

        # Use Jinja2 template
        params:
          compute_path:
            method: template
            params:
              template: "{{ meta.category }}/{{ meta.id }}-{{ file_name }}"

        # Use only file name (flat structure)
        params:
          compute_path:
            method: file_name
        ```
    """
    # Extract file_name from data or use provided override
    file_name = raw_file_name or data.get("file_name")

    # Extract MIME type from headers (use lowercase keys for case-insensitive access)
    headers = {k.lower(): v for k, v in data.get("headers", {}).items()}
    mime_type = normalize_mimetype(headers.get("content-type"))

    compute_path = context.params.get("compute_path", {})
    method = compute_path.get("method", "url_path")
    params = compute_path.get("params", {})

    if method == "template":
        template = params.get("template")
        if not template:
            raise ValueError(
                "compute_path.params.template is required for template method"
            )

        # Build template context with useful variables
        template_data = {
            **data,
            "content_hash": content_hash,
            "file_name": file_name,
        }
        rendered = render_template(template, template_data)
        if not rendered:
            raise ValueError(f"Template rendered to empty string: {template}")
        dir_part = os.path.dirname(rendered)
        name_part = os.path.basename(rendered)
        if not name_part:
            raise ValueError(f"Template must include a file name: {template}")
        # Extension from rendered template name, fallback to mime_type
        extension = _get_file_extension(name_part, mime_type)
        final_name = (
            safe_filename(name_part, extension=extension) if safe_names else name_part
        )
        return Path(dir_part) / final_name if dir_part else Path(final_name)

    elif method == "url_path":
        # Use the URL path with optional domain prefix and strip_prefix
        include_domain = params.get("include_domain", False)
        strip_prefix = params.get("strip_prefix", "").strip("/")

        url = data.get("url", "")
        if not url:
            raise ValueError("url_path method requires 'url' in data")
        url_parts = urlparse(url)
        path = unquote(url_parts.path).strip("/")

        # Strip prefix if specified
        if strip_prefix and path.startswith(strip_prefix):
            path = path[len(strip_prefix) :].strip("/")

        # Split into directory and filename
        dir_part = os.path.dirname(path)
        name_part = os.path.basename(path)
        if not name_part:
            raise ValueError(f"Could not extract file name from URL path: {url}")

        # Optionally include domain
        if include_domain:
            dir_part = join_relpaths(url_parts.netloc, dir_part)

        # Extension from URL basename, fallback to mime_type
        extension = _get_file_extension(name_part, mime_type)
        final_name = (
            safe_filename(name_part, extension=extension) if safe_names else name_part
        )
        return Path(dir_part) / final_name if dir_part else Path(final_name)

    elif method == "file_name":
        # Use only the file name (flat structure)
        # Fall back to "data" if no file_name available
        file_name = file_name or "data"
        # Extension from provided file_name, fallback to mime_type
        extension = _get_file_extension(file_name, mime_type)
        final_name = (
            safe_filename(file_name, extension=extension) if safe_names else file_name
        )
        return Path(final_name)

    else:
        raise ValueError(f"Unknown compute_path method: {method}")


def _get_file_extension(file_name: str | None, mime_type: str | None) -> str:
    """Determine file extension from filename or MIME type."""
    if file_name is not None:
        _, extension = os.path.splitext(file_name)
        extension = extension.replace(".", "")
        if len(extension) > 1:
            return extension
    if mime_type is not None:
        extension = mimetypes.guess_extension(mime_type)
        if extension is not None:
            extension = extension.replace(".", "")
            if len(extension) > 1:
                return extension
    return "raw"


@register("directory")
def directory(context: Context, data: dict[str, Any]) -> None:
    """Store collected files to a local directory.

    Saves files to a directory structure organized by crawler name.
    Also stores metadata as a JSON sidecar file.

    Args:
        context: The crawler context.
        data: Must contain content_hash from a fetched response.

    Params:
        path: Custom storage path (default: {base_path}/store/{crawler_name}).
        compute_path: Configure how file paths are computed.
            method: The path computation method (default: "url_path")
                - "url_path": Use the URL path
                - "template": Use Jinja2 template with data context
                - "file_name": Use only the file name (flat structure)
            params: Method-specific parameters
                For url_path:
                    include_domain: bool - Include domain as path prefix (default: false)
                    strip_prefix: str - Strip this prefix from the path
                For template:
                    template: str - Jinja2 template with data context

    Example:
        ```yaml
        pipeline:
          store:
            method: directory
            params:
              path: /data/documents
              compute_path:
                method: url_path
                params:
                  include_domain: true
                  strip_prefix: "/api/v1"
        ```
    """
    with context.http.rehash(data) as result:
        if not result.ok:
            return

        content_hash = data.get("content_hash")
        if content_hash is None:
            context.emit_warning("No content hash in data.")
            return

        base_path = Path(_get_directory_path(context))

        # Compute the relative path (helper uses result.file_name as fallback)
        relative_path = _compute_file_path(
            context, data, content_hash, result.file_name
        )

        # Build full path and ensure parent directories exist
        file_path = base_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Check for collision: file exists with different content
        if file_path.exists():
            with open(file_path, "rb") as fh:
                existing_hash = make_checksum(fh)
            if existing_hash != content_hash:
                # Add 8-char hash suffix to avoid overwriting
                suffix = content_hash[:8]
                new_name = f"{file_path.stem}_{suffix}{file_path.suffix}"
                file_path = file_path.parent / new_name
                relative_path = relative_path.parent / new_name

        data["_file_name"] = str(relative_path)

        if not file_path.exists():
            with result.local_path() as p:
                shutil.copyfile(p, file_path)

        context.log.info("Store [directory]", file=str(relative_path))

        # Store metadata as sidecar JSON (named by content_hash for easy lookup)
        meta_path = file_path.parent / f"{content_hash}.json"
        with open(meta_path, "w") as fh:
            json.dump(data, fh)

        # Mark incremental completion
        context.mark_emit_complete(data)
        context.emit(data=data)


@register("lakehouse")
def lakehouse(context: Context, data: dict[str, Any]) -> None:
    """Store collected file in the ftm-lakehouse archive.

    Stores files in a structured archive with metadata tracking,
    suitable for integration with Aleph and other FTM-based systems.

    Args:
        context: The crawler context.
        data: Must contain content_hash from a fetched response.

    Params:
        compute_path: Configure how file keys are computed.
            method: The path computation method (default: "url_path")
                - "url_path": Use the URL path
                - "template": Use Jinja2 template with data context
                - "file_name": Use only the file name (flat structure)
            params: Method-specific parameters
                For url_path:
                    include_domain: bool - Include domain as path prefix (default: false)
                    strip_prefix: str - Strip this prefix from the path
                For template:
                    template: str - Jinja2 template with data context
        make_entities: Create FTM entities from stored files (default: true)

    Example:
        ```yaml
        pipeline:
          store:
            method: lakehouse
            params:
              compute_path:
                method: url_path
                params:
                  strip_prefix: "/api/v1"
        ```
    """
    with context.http.rehash(data) as result:
        if not result.ok:
            return

        content_hash = data.get("content_hash")
        if content_hash is None:
            context.emit_warning("No content hash in data.")
            return

        # Compute the file key using compute_path config (no safe_filename for lakehouse)
        relative_path = _compute_file_path(
            context, data, content_hash, result.file_name, safe_names=False
        )
        file_key = str(relative_path)
        file_name = relative_path.name

        # Extract MIME type from headers for lakehouse metadata
        headers = {k.lower(): v for k, v in data.get("headers", {}).items()}
        mime_type = normalize_mimetype(headers.get("content-type"))

        # Store file in lakehouse archive with metadata. If the archive is the
        # same as the memorious intermediary archive (which is the default), the
        # file already exists and only the metadata is stored.
        with result.local_path() as local_path:
            file = context.archive.store(
                local_path,
                name=file_name,
                key=file_key,
                mimetype=mime_type,
            )

        # Generate entities
        make_entities = context.params.get("make_entities", True)
        if make_entities:
            entities = [file.to_entity(), *file.make_parents()]
            context.entities.add_many(entities, origin=CRAWL_ORIGIN)

        context.log.info(
            "Store [lakehouse]", file=file_name, key=file_key, checksum=file.checksum
        )

        # Mark incremental completion
        context.mark_emit_complete(data)
        context.emit(data=data)


@register("cleanup_archive")
def cleanup_archive(context: Context, data: dict[str, Any]) -> None:
    """Remove a blob from the archive.

    Deletes a file from the archive after processing is complete.
    Useful for cleaning up temporary files.

    Args:
        context: The crawler context.
        data: Must contain content_hash of file to delete.

    Example:
        ```yaml
        pipeline:
          cleanup:
            method: cleanup_archive
        ```
    """
    content_hash = data.get("content_hash")
    if content_hash is None:
        context.emit_warning("No content hash in data.")
        return
    file_info = context.archive.get(content_hash)
    if file_info:
        try:
            context.archive.delete(file_info)
        except NotImplementedError:
            context.log.warning("File deletion not supported by storage backend")


@register("store")
def store(context: Context, data: dict[str, Any]) -> None:
    """Store with configurable backend and incremental marking.

    A flexible store operation that delegates to other storage methods
    and marks incremental completion when the target stage is reached.

    Args:
        context: The crawler context.
        data: Must contain content_hash from a fetched response.

    Params:
        operation: Storage operation name (default: "directory").
            Options: "directory", "lakehouse"

    Example:
        ```yaml
        pipeline:
          store:
            method: store
            params:
              operation: lakehouse
        ```

    Note:
        Incremental completion is marked automatically by the underlying
        storage operations (directory, lakehouse).
    """
    operation = context.params.get("operation", "directory")

    if operation == "directory":
        directory(context, data)
    elif operation == "lakehouse":
        lakehouse(context, data)
    else:
        context.log.error("Unknown store operation", operation=operation)
