import numbers
import re

from dateutil.parser import parse
from normality import stringify


class ContextCheck(object):
    def __init__(self, context):
        self.context = context

    def shout(self, msg, strict=False, **kwargs):
        if strict:
            raise ValueError(msg)
        else:
            self.context.log.info(msg, **kwargs)

    def is_not_empty(self, value, strict=False):
        """if value is not empty"""
        value = stringify(value)
        if value is not None:
            return
        self.shout("Value is empty", strict, value=value)

    def is_numeric(self, value, strict=False):
        """if value is numeric"""
        value = stringify(value)
        if value is not None:
            if value.isnumeric():
                return
        self.shout("Value is not numeric", strict, value=value)

    def is_integer(self, value, strict=False):
        """if value is an integer"""
        if value is not None:
            if isinstance(value, numbers.Number):
                return
        value = stringify(value)
        if value is not None and value.isnumeric():
            return
        self.shout("Value is not an integer", strict, value=value)

    def match_date(self, value, strict=False):
        """if value is a date"""
        value = stringify(value)
        try:
            parse(value)
        except Exception:
            self.shout("Value is not a valid date", strict, value=value)

    def match_regexp(self, value, q, strict=False):
        """if value matches a regexp q"""
        value = stringify(value)
        mr = re.compile(q)
        if value is not None:
            if mr.match(value):
                return
        self.shout("Value not matching the regexp", strict, value=value, pattern=q)

    def has_length(self, value, q, strict=False):
        """if value has a length of q"""
        value = stringify(value)
        if value is not None:
            if len(value) == q:
                return
        self.shout("Value not matching length", strict, value=value, expected=q)

    def must_contain(self, value, q, strict=False):
        """if value must contain q"""
        if value is not None:
            if value.find(q) != -1:
                return
        self.shout("Value does not contain expected", strict, value=value, expected=q)
