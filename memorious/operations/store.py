"""File storage operations.

This module provides operations for storing crawled files to various
backends including local directories and ftm-lakehouse archives.
"""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
from typing import TYPE_CHECKING, Any

import httpx
from ftm_lakehouse import get_lakehouse
from normality import safe_filename
from rigour.mime import normalize_mimetype

from memorious.operations import register

if TYPE_CHECKING:
    from memorious.logic.context import Context


def _get_directory_path(context: Context) -> str:
    """Get the storage path for directory storage."""
    path = os.path.join(context.settings.base_path, "store")
    path = context.params.get("path", path)
    path = os.path.join(path, context.crawler.name)
    path = os.path.abspath(os.path.expandvars(path))
    try:
        os.makedirs(path)
    except Exception:
        pass
    return path


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

    Example:
        ```yaml
        pipeline:
          store:
            method: directory
            params:
              path: /data/documents
        ```
    """
    with context.http.rehash(data) as result:
        if not result.ok:
            return

        content_hash = data.get("content_hash")
        if content_hash is None:
            context.emit_warning("No content hash in data.")
            return

        path = _get_directory_path(context)
        file_name = data.get("file_name", result.file_name)
        # httpx.Headers is case-insensitive
        headers = httpx.Headers(data.get("headers", {}))
        mime_type = normalize_mimetype(headers.get("content-type"))
        extension = _get_file_extension(file_name, mime_type)
        file_name = file_name or "data"
        file_name = safe_filename(file_name, extension=extension)
        file_name = "%s.%s" % (content_hash, file_name)
        data["_file_name"] = file_name
        file_path = os.path.join(path, file_name)
        if not os.path.exists(file_path):
            with result.local_path() as p:
                shutil.copyfile(p, file_path)

        context.log.info("Store [directory]", file=file_name)
        meta_path = os.path.join(path, "%s.json" % content_hash)
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
        uri: Custom lakehouse URI (default: context.archive).

    Example:
        ```yaml
        pipeline:
          store:
            method: lakehouse
            params:
              uri: s3://bucket/archive
        ```
    """
    with context.http.rehash(data) as result:
        if not result.ok:
            return

        content_hash = data.get("content_hash")
        if content_hash is None:
            context.emit_warning("No content hash in data.")
            return

        file_name = data.get("file_name", result.file_name)
        # httpx.Headers is case-insensitive
        headers = httpx.Headers(data.get("headers", {}))
        mime_type = normalize_mimetype(headers.get("content-type"))
        extension = _get_file_extension(file_name, mime_type)
        file_name = file_name or "data"
        file_name = safe_filename(file_name, extension=extension)

        # Use custom URI if provided, otherwise use context archive
        uri = context.params.get("uri")
        if uri:
            archive = get_lakehouse(uri).get_dataset(context.crawler.name).archive
        else:
            archive = context.archive

        # Store file in lakehouse archive with metadata
        with result.local_path() as local_path:
            file_info = archive.archive_file(
                local_path,
                origin="memorious",
                name=file_name,
                mimetype=mime_type,
                source_url=data.get("url"),
            )

        context.log.info(
            "Store [lakehouse]", file=file_name, checksum=file_info.checksum
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
    file_info = context.archive.lookup_file(content_hash)
    if file_info:
        try:
            context.archive.delete_file(file_info)
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
