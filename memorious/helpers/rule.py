"""URL/content filtering rules as Pydantic models.

This module provides a rule system for filtering HTTP responses based on
URL patterns, domains, MIME types, and XPath expressions. Rules can be
combined using boolean operators (and, or, not).

Example YAML configuration:
    ```yaml
    rules:
      and:
        - domain: example.com
        - not:
            or:
              - mime_group: images
              - pattern: ".*\\.pdf$"
    ```
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Any, Union
from urllib.parse import urlparse

from lxml import html
from pydantic import BaseModel, Field, field_validator
from rigour.mime import normalize_mimetype

from memorious.exc import RuleParsingException
from memorious.logic.mime import GROUPS

if TYPE_CHECKING:
    from memorious.logic.http import ContextHttpResponse


class BaseRule(BaseModel):
    """Base class for all rule types."""

    model_config = {"extra": "forbid"}

    def apply(self, response: ContextHttpResponse) -> bool:
        """Apply this rule to an HTTP response.

        Args:
            response: The HTTP response to check.

        Returns:
            True if the response matches this rule, False otherwise.
        """
        raise NotImplementedError


class OrRule(BaseRule):
    """Match if any nested rule matches.

    Example:
        ```yaml
        or:
          - domain: example.com
          - domain: example.org
        ```
    """

    any_of: list[AnyRule] = Field(alias="or")

    def apply(self, response: ContextHttpResponse) -> bool:
        return any(rule.apply(response) for rule in self.any_of)


class AndRule(BaseRule):
    """Match if all nested rules match.

    Example:
        ```yaml
        and:
          - domain: example.com
          - mime_group: documents
        ```
    """

    all_of: list[AnyRule] = Field(alias="and")

    def apply(self, response: ContextHttpResponse) -> bool:
        return all(rule.apply(response) for rule in self.all_of)


class NotRule(BaseRule):
    """Invert a nested rule.

    Example:
        ```yaml
        not:
          mime_group: images
        ```
    """

    negate: AnyRule = Field(alias="not")

    def apply(self, response: ContextHttpResponse) -> bool:
        return not self.negate.apply(response)


class MatchAllRule(BaseRule):
    """Always matches (default rule).

    Example:
        ```yaml
        match_all: {}
        ```
    """

    match_all: dict[str, Any] = Field(default_factory=dict)

    def apply(self, response: ContextHttpResponse) -> bool:
        return True


class DomainRule(BaseRule):
    """Match URLs from a specific domain (including subdomains).

    Example:
        ```yaml
        domain: example.com
        ```

    This matches example.com, www.example.com, sub.example.com, etc.
    """

    domain: str

    @field_validator("domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        """Normalize the domain value."""
        if not v:
            raise ValueError("Domain cannot be empty")
        pr = urlparse(v)
        domain = pr.hostname or pr.path
        return domain.strip(".").lower()

    def apply(self, response: ContextHttpResponse) -> bool:
        if not response.url:
            return False
        pr = urlparse(response.url)
        hostname = pr.hostname
        if hostname is None:
            return False
        hostname = hostname.strip(".").lower()
        if hostname == self.domain:
            return True
        if hostname.endswith(f".{self.domain}"):
            return True
        return False


class MimeTypeRule(BaseRule):
    """Match a specific MIME type.

    Example:
        ```yaml
        mime_type: application/pdf
        ```
    """

    mime_type: str
    _normalized: str | None = None

    def model_post_init(self, __context: Any) -> None:
        self._normalized = normalize_mimetype(self.mime_type)

    def apply(self, response: ContextHttpResponse) -> bool:
        return response.content_type == self._normalized


class MimeGroupRule(BaseRule):
    """Match MIME type group (documents, images, assets, etc).

    Example:
        ```yaml
        mime_group: documents
        ```

    Available groups are defined in memorious.logic.mime.GROUPS.
    """

    mime_group: str

    def apply(self, response: ContextHttpResponse) -> bool:
        ct = response.content_type or ""
        if ct.startswith(f"{self.mime_group}/"):
            return True
        return ct in GROUPS.get(self.mime_group, [])


class PatternRule(BaseRule):
    """Match URL against a regex pattern.

    Example:
        ```yaml
        pattern: "https://example.com/docs/.*\\.pdf$"
        ```
    """

    pattern: str
    _compiled: re.Pattern[str] | None = None

    def model_post_init(self, __context: Any) -> None:
        self._compiled = re.compile(self.pattern, re.I | re.U)

    def apply(self, response: ContextHttpResponse) -> bool:
        if not response.url or self._compiled is None:
            return False
        return bool(self._compiled.match(response.url))


class XpathRule(BaseRule):
    """Match if XPath expression finds elements in the response body.

    Example:
        ```yaml
        xpath: '//div[@class="article"]/text()'
        ```
    """

    xpath: str

    def apply(self, response: ContextHttpResponse) -> bool:
        if not response.text:
            return False
        try:
            doc = html.fromstring(response.text)
            result = doc.xpath(self.xpath)
            return bool(result)
        except Exception:
            return False


# Union of all rule types for recursive definitions
AnyRule = Annotated[
    Union[
        OrRule,
        AndRule,
        NotRule,
        MatchAllRule,
        DomainRule,
        MimeTypeRule,
        MimeGroupRule,
        PatternRule,
        XpathRule,
    ],
    Field(discriminator=None),
]

# Update forward references for recursive types
OrRule.model_rebuild()
AndRule.model_rebuild()
NotRule.model_rebuild()


# Rule name mapping for parsing specs
RULE_TYPES: dict[str, type[BaseRule]] = {
    "or": OrRule,
    "any": OrRule,
    "and": AndRule,
    "all": AndRule,
    "not": NotRule,
    "match_all": MatchAllRule,
    "domain": DomainRule,
    "mime_type": MimeTypeRule,
    "mime_group": MimeGroupRule,
    "pattern": PatternRule,
    "xpath": XpathRule,
}


def parse_rule(spec: dict[str, Any]) -> AnyRule:
    """Parse a rule specification dict into a Rule model.

    Args:
        spec: Dictionary with a single key identifying the rule type.

    Returns:
        A parsed rule instance.

    Raises:
        RuleParsingException: If the spec is invalid.

    Example:
        ```python
        rule = parse_rule({"domain": "example.com"})
        if rule.apply(response):
            print("Matched!")
        ```
    """
    if not isinstance(spec, dict):
        raise RuleParsingException(f"Not a valid rule: {spec!r}")
    if len(spec) > 1:
        raise RuleParsingException(f"Ambiguous rules (multiple keys): {spec!r}")
    if len(spec) == 0:
        raise RuleParsingException("Empty rule specification")

    rule_name, value = next(iter(spec.items()))

    if rule_name not in RULE_TYPES:
        raise RuleParsingException(f"Unknown rule type: {rule_name}")

    rule_cls = RULE_TYPES[rule_name]

    try:
        # Handle list rules (or, and)
        if rule_name in ("or", "any"):
            if not isinstance(value, list):
                raise RuleParsingException(f"'{rule_name}' rule requires a list")
            children = [parse_rule(child) for child in value]
            return OrRule(**{"or": children})

        elif rule_name in ("and", "all"):
            if not isinstance(value, list):
                raise RuleParsingException(f"'{rule_name}' rule requires a list")
            children = [parse_rule(child) for child in value]
            return AndRule(**{"and": children})

        elif rule_name == "not":
            if not isinstance(value, dict):
                raise RuleParsingException("'not' rule requires a dict")
            child = parse_rule(value)
            return NotRule(**{"not": child})

        elif rule_name == "match_all":
            return MatchAllRule(match_all=value or {})

        else:
            # Simple rules with a single value
            return rule_cls(**{rule_name: value})

    except Exception as e:
        if isinstance(e, RuleParsingException):
            raise
        raise RuleParsingException(f"Failed to parse rule '{rule_name}': {e}") from e
