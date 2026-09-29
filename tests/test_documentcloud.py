import json

import httpx
import pytest

from memorious.exc import ParseError
from memorious.operations.documentcloud import documentcloud_query


class TestDocumentCloud(object):
    @pytest.mark.xfail(
        reason="flaky: documentcloud.org is not reliably reachable from all CIs",
        raises=(json.JSONDecodeError, httpx.HTTPError, ParseError),
        strict=False,
    )
    def test_query(self, context, mocker):
        data = {}
        context.params["query"] = "money"

        mocker.patch.object(context, "emit")
        mocker.patch.object(context, "recurse")

        documentcloud_query(context, data)
        assert context.emit.call_count >= 10
        assert context.recurse.call_count == 1
        context.recurse.assert_called_once_with(data={"query": "money", "page": 2})
