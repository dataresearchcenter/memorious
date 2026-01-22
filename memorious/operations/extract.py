"""Archive extraction operations.

This module provides operations for extracting files from compressed
archives (zip, tar, 7z).
"""

from __future__ import annotations

import os
import subprocess
import tarfile
import zipfile
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any

from banal import ensure_list

from memorious.operations import register
from memorious.util import random_filename

if TYPE_CHECKING:
    from memorious.logic.context import Context

ZIP_MIME_TYPES = [
    "application/zip",
    "application/x-zip",
    "multipart/x-zip",
    "application/zip-compressed",
    "application/x-zip-compressed",
]

TAR_MIME_TYPES = [
    "application/tar",
    "application/x-tar",
    "application/x-tgz",
    "application/x-gtar",
    "application/x-gzip",
    "application/gzip",
]

SEVENZIP_MIME_TYPES = ["application/x-7z-compressed", "application/7z-compressed"]


def extract_zip(file_path: str, extract_dir: str, context: Context) -> list[str]:
    """Extract files from a ZIP archive."""
    files = []
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        if zip_ref.testzip() is not None:
            context.log.warning("Bad zip file", file=file_path)
        zip_ref.extractall(extract_dir)
        for name in zip_ref.namelist():
            extracted = os.path.join(extract_dir, name)
            if os.path.isfile(extracted):
                files.append(extracted)
    return files


def extract_tar(file_path: str, extract_dir: str, context: Context) -> list[str]:
    """Extract files from a TAR archive."""
    files = []
    with tarfile.open(file_path, "r:*") as tar_ref:
        for name in tar_ref.getnames():
            if name.startswith("..") or name.startswith("/"):
                context.log.info(
                    "Bad path while extracting archive", path=name, file=file_path
                )
            else:
                tar_ref.extract(name, extract_dir)
                extracted = os.path.join(extract_dir, name)
                if os.path.isfile(extracted):
                    files.append(extracted)
    return files


def extract_7zip(file_path: str, extract_dir: str, context: Context) -> list[str]:
    """Extract files from a 7z archive."""
    files = []
    return_code = subprocess.call(["7z", "x", file_path, "-r", "-o%s" % extract_dir])
    if return_code != 0:
        context.log.warning("Couldn't extract file", file=file_path)
        return files
    for root, _, filenames in os.walk(extract_dir):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files


def _test_fname(wildcards: list[str], path: str) -> bool:
    """Check if path matches any wildcard pattern."""
    for pattern in wildcards:
        if fnmatch(path, pattern):
            return True
    return False


@register("extract")
def extract(context: Context, data: dict[str, Any]) -> None:
    """Extract files from a compressed archive.

    Supports ZIP, TAR (including gzip/bzip2), and 7z archives.
    Emits each extracted file as a separate data item.

    Args:
        context: The crawler context.
        data: Must contain cached HTTP response data.

    Params:
        wildcards (optional): List of shell-style patterns to filter extracted files.

    Example:
        ```yaml
        pipeline:
          extract:
            method: extract
            params:
              wildcards:
                - "*.pdf"
                - "*.doc"
                - "documents/*"
            handle:
              pass: store
        ```
    """
    with context.http.rehash(data) as result:
        if not result.ok:
            return

        with result.local_path() as local_file:
            file_path = str(local_file)
            content_type = result.content_type
            extract_dir = random_filename(context.work_path)

            if content_type in ZIP_MIME_TYPES:
                extracted_files = extract_zip(file_path, extract_dir, context)
            elif content_type in TAR_MIME_TYPES:
                extracted_files = extract_tar(file_path, extract_dir, context)
            elif content_type in SEVENZIP_MIME_TYPES:
                extracted_files = extract_7zip(file_path, extract_dir, context)
            else:
                context.log.warning(
                    "Unsupported archive content type", content_type=content_type
                )
                return

            wildcards = ensure_list(context.params.get("wildcards")) or None
            for path in extracted_files:
                if wildcards is None or _test_fname(wildcards, path):
                    relative_path = os.path.relpath(path, extract_dir)
                    content_hash = context.store_file(path)
                    data["content_hash"] = content_hash
                    data["file_name"] = relative_path
                    context.emit(data=data.copy())
