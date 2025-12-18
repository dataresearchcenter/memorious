# Operations Reference

API documentation for all built-in operations.

## Initializers

Operations for starting crawler pipelines.

::: memorious.operations.initializers.seed

::: memorious.operations.initializers.enumerate

::: memorious.operations.initializers.tee

::: memorious.operations.initializers.sequence

::: memorious.operations.initializers.dates

---

## Fetch

Operations for making HTTP requests.

::: memorious.operations.fetch.fetch

::: memorious.operations.fetch.session

::: memorious.operations.fetch.post

::: memorious.operations.fetch.post_json

::: memorious.operations.fetch.post_form

---

## Parse

Operations for parsing responses.

::: memorious.operations.parse.parse

::: memorious.operations.parse.parse_listing

::: memorious.operations.parse.parse_jq

::: memorious.operations.parse.parse_csv

::: memorious.operations.parse.parse_xml

---

## Clean

Operations for cleaning data.

::: memorious.operations.clean.clean

::: memorious.operations.clean.clean_html

---

## Extract

Operations for extracting archives.

::: memorious.operations.extract.extract

---

## Regex

Operations for regex extraction.

::: memorious.operations.regex.regex_groups

---

## Store

Operations for storing data.

::: memorious.operations.store.store

::: memorious.operations.store.directory

::: memorious.operations.store.lakehouse

::: memorious.operations.store.cleanup_archive

---

## Debug

Operations for debugging.

::: memorious.operations.debug.inspect

::: memorious.operations.debug.ipdb

---

## FTP

::: memorious.operations.ftp.ftp_fetch

---

## WebDAV

::: memorious.operations.webdav.dav_index

---

## DocumentCloud

::: memorious.operations.documentcloud.documentcloud_query

::: memorious.operations.documentcloud.documentcloud_mark_processed

---

## Aleph

Operations for Aleph integration.

::: memorious.operations.aleph.aleph_emit

::: memorious.operations.aleph.aleph_emit_document

::: memorious.operations.aleph.aleph_folder

::: memorious.operations.aleph.aleph_emit_entity

---

## FTM Store

Operations for FollowTheMoney entity storage.

::: memorious.operations.ftm.ftm_store

::: memorious.operations.ftm.ftm_load_aleph

---

## Helpers

Utility modules for operations.

### Pagination

::: memorious.helpers.pagination
    options:
      show_root_heading: true
      members:
        - get_paginated_url
        - paginate

### Casting

::: memorious.helpers.casting
    options:
      show_root_heading: true
      members:
        - cast_value
        - cast_dict
        - ensure_date

### XPath

::: memorious.helpers.xpath
    options:
      show_root_heading: true
      members:
        - extract_xpath

### Template

::: memorious.helpers.template
    options:
      show_root_heading: true
      members:
        - render_template

### Forms

::: memorious.helpers.forms
    options:
      show_root_heading: true
      members:
        - extract_form

### Regex

::: memorious.helpers.regex
    options:
      show_root_heading: true
      members:
        - regex_first

### YAML

::: memorious.helpers.yaml
    options:
      show_root_heading: true
      members:
        - load_yaml
        - IncludeLoader

---

## Registry

::: memorious.operations.register
    options:
      show_root_heading: true

::: memorious.operations.resolve_operation
    options:
      show_root_heading: true

::: memorious.operations.list_operations
    options:
      show_root_heading: true

---

## Incremental

::: memorious.logic.incremental
    options:
      show_root_heading: true
      members:
        - should_skip_incremental
        - mark_incremental_complete
