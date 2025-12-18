import json
import mimetypes
import os
import shutil

from ftm_lakehouse import get_lakehouse
from normality import safe_filename
from requests.structures import CaseInsensitiveDict
from rigour.mime import normalize_mimetype


def _get_directory_path(context):
    """Get the storage path from the output."""
    path = os.path.join(context.settings.base_path, "store")
    path = context.params.get("path", path)
    path = os.path.join(path, context.crawler.name)
    path = os.path.abspath(os.path.expandvars(path))
    try:
        os.makedirs(path)
    except Exception:
        pass
    return path


def _get_file_extension(file_name, mime_type):
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


def directory(context, data):
    """Store the collected files to a given directory."""
    with context.http.rehash(data) as result:
        if not result.ok:
            return

        content_hash = data.get("content_hash")
        if content_hash is None:
            context.emit_warning("No content hash in data.")
            return

        path = _get_directory_path(context)
        file_name = data.get("file_name", result.file_name)
        mime_type = normalize_mimetype(
            CaseInsensitiveDict(data.get("headers", {})).get("content-type")
        )
        extension = _get_file_extension(file_name, mime_type)
        file_name = file_name or "data"
        file_name = safe_filename(file_name, extension=extension)
        file_name = "%s.%s" % (content_hash, file_name)
        data["_file_name"] = file_name
        file_path = os.path.join(path, file_name)
        if not os.path.exists(file_path):
            with result.local_path() as p:
                shutil.copyfile(p, file_path)

        context.log.info("Store [directory]: %s", file_name)
        meta_path = os.path.join(path, "%s.json" % content_hash)
        with open(meta_path, "w") as fh:
            json.dump(data, fh)


def lakehouse(context, data):
    """Store the collected file in the ftm-lakehouse archive.

    Optional params:
        uri: Custom lakehouse URI to store files (default: context.archive)
    """
    with context.http.rehash(data) as result:
        if not result.ok:
            return

        content_hash = data.get("content_hash")
        if content_hash is None:
            context.emit_warning("No content hash in data.")
            return

        file_name = data.get("file_name", result.file_name)
        mime_type = normalize_mimetype(
            CaseInsensitiveDict(data.get("headers", {})).get("content-type")
        )
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
        # file_info = File(name=file_name, checksum=content_hash)
        with result.local_path() as local_path:
            file_info = archive.archive_file(
                local_path,
                origin="memorious",
                name=file_name,
                mimetype=mime_type,
                source_url=data.get("url"),
            )

        context.log.info("Store [lakehouse]: %s (%s)", file_name, file_info.checksum)
        context.emit(data=data)


def cleanup_archive(context, data):
    """Remove a blob from the archive after we're done with it"""
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
