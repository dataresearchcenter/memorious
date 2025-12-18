from collections import namedtuple

import pytest

from memorious.exc import RuleParsingException
from memorious.helpers.rule import (
    AndRule,
    DomainRule,
    OrRule,
    PatternRule,
    XpathRule,
    parse_rule,
)

spec = {
    "and": [
        {"domain": "occrp.org"},
        {
            "not": {
                "or": [
                    {"domain": "vis.occrp.org"},
                    {"domain": "tech.occrp.org"},
                    {"domain": "data.occrp.org"},
                    {"mime_group": "assets"},
                    {"mime_group": "images"},
                    {"pattern": "https://www.occrp.org/en/component/.*"},
                    {"pattern": "https://www.occrp.org/en/donate.*"},
                    {"pattern": "https://www.occrp.org/.*start=.*"},
                    {"pattern": "https://www.occrp.org/ru/.*"},
                    {"xpath": '//div[@title="buyer-name"]/text()'},
                ]
            }
        },
    ]
}

invalid_spec = {
    "and": [{"domain": "occrp.org"}, {"not": {"domain": "vis.occrp.org"}}],
    "not": {"mime_group": "images"},
}


class TestRule:
    def test_parse_rule_invalid(self):
        with pytest.raises(RuleParsingException):
            parse_rule(invalid_spec)

    def test_parse_rule_complex(self):
        rule = parse_rule(spec)
        assert isinstance(rule, AndRule)

    def test_parse_rule(self):
        rule = parse_rule({"domain": "example.com"})
        assert isinstance(rule, DomainRule)
        assert rule.domain == "example.com"

    def test_parse_or_rule(self):
        rule = parse_rule({"or": [{"domain": "a.com"}, {"domain": "b.com"}]})
        assert isinstance(rule, OrRule)
        assert len(rule.any_of) == 2

    def test_parse_invalid(self):
        with pytest.raises(RuleParsingException):
            parse_rule("not a dict")
        with pytest.raises(RuleParsingException):
            parse_rule({})
        with pytest.raises(RuleParsingException):
            parse_rule({"unknown_rule": "value"})


class TestDomainRule:
    def test_domain_rule(self):
        rule = DomainRule(domain="occrp.org")
        Response = namedtuple("Response", "url")
        res = Response(url="http://occrp.org")
        assert rule.apply(res)
        res = Response(url="http://not-occrp.org")
        assert rule.apply(res) is False

    def test_subdomain_match(self):
        rule = DomainRule(domain="occrp.org")
        Response = namedtuple("Response", "url")
        res = Response(url="http://www.occrp.org/page")
        assert rule.apply(res)
        res = Response(url="http://sub.domain.occrp.org")
        assert rule.apply(res)

    def test_no_url(self):
        rule = DomainRule(domain="occrp.org")
        Response = namedtuple("Response", "url")
        res = Response(url=None)
        assert rule.apply(res) is False


class TestPatternRule:
    def test_url_pattern(self):
        rule = PatternRule(pattern="https://www.occrp.org/en/donate.*")
        Response = namedtuple("Response", "url")
        res = Response(url="https://www.occrp.org/en/donate.html")
        assert rule.apply(res)
        res = Response(url="http://not-occrp.org")
        assert rule.apply(res) is False

    def test_case_insensitive(self):
        rule = PatternRule(pattern="https://example.com/.*")
        Response = namedtuple("Response", "url")
        res = Response(url="HTTPS://EXAMPLE.COM/page")
        assert rule.apply(res)


class TestXpathRule:
    def test_xpath(self):
        rule = XpathRule(xpath='//div[@class="section-title"]/text()')
        Response = namedtuple("Response", "text")
        res = Response(text='<div class="section-title">text</div>')
        assert rule.apply(res)

    def test_xpath_no_match(self):
        rule = XpathRule(xpath='//div[@class="not-found"]')
        Response = namedtuple("Response", "text")
        res = Response(text='<div class="other">text</div>')
        assert rule.apply(res) is False

    def test_xpath_no_text(self):
        rule = XpathRule(xpath="//div")
        Response = namedtuple("Response", "text")
        res = Response(text=None)
        assert rule.apply(res) is False


class TestComplexRules:
    def test_and_rule(self):
        rule = parse_rule(
            {"and": [{"domain": "example.com"}, {"pattern": ".*/docs/.*"}]}
        )
        Response = namedtuple("Response", ["url", "content_type"])
        res = Response(url="http://example.com/docs/file.pdf", content_type="text/html")
        assert rule.apply(res)
        res = Response(
            url="http://example.com/other/file.pdf", content_type="text/html"
        )
        assert rule.apply(res) is False

    def test_or_rule(self):
        rule = parse_rule({"or": [{"domain": "a.com"}, {"domain": "b.com"}]})
        Response = namedtuple("Response", "url")
        assert rule.apply(Response(url="http://a.com"))
        assert rule.apply(Response(url="http://b.com"))
        assert rule.apply(Response(url="http://c.com")) is False

    def test_not_rule(self):
        rule = parse_rule({"not": {"domain": "blocked.com"}})
        Response = namedtuple("Response", "url")
        assert rule.apply(Response(url="http://allowed.com"))
        assert rule.apply(Response(url="http://blocked.com")) is False

    def test_nested_rules(self):
        # Match occrp.org but not subdomains vis/tech/data
        rule = parse_rule(spec)
        Response = namedtuple("Response", ["url", "content_type", "text"])
        res = Response(
            url="http://www.occrp.org/article",
            content_type="text/html",
            text="<html></html>",
        )
        assert rule.apply(res)
        res = Response(
            url="http://vis.occrp.org/chart",
            content_type="text/html",
            text="<html></html>",
        )
        assert rule.apply(res) is False
