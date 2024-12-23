# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from re import (
    IGNORECASE,
    MULTILINE,
    UNICODE,
    VERBOSE,
    Match,
    Pattern,
)
from typing import Any, Optional, TypedDict, Union

from typing_extensions import Self

TupleStr = tuple[str, ...]
DictData = dict[str, Any]
DictStr = dict[str, str]
Matrix = dict[str, Union[list[str], list[int]]]


class Context(TypedDict):
    params: dict[str, Any]
    jobs: dict[str, Any]


@dataclass(frozen=True)
class CallerRe:
    """Caller dataclass that catching result from the matching regex with the
    Re.RE_CALLER value.
    """

    full: str
    caller: str
    caller_prefix: Optional[str]
    caller_last: str
    post_filters: str

    @classmethod
    def from_regex(cls, match: Match[str]) -> Self:
        """Class construct from matching result.

        :rtype: Self
        """
        return cls(full=match.group(0), **match.groupdict())


class Re:
    """Regular expression config for this package."""

    # NOTE:
    #   Regular expression:
    #       - Version 1:
    #         \${{\s*(?P<caller>[a-zA-Z0-9_.\s'\"\[\]\(\)\-\{}]+?)\s*(?P<post_filters>(?:\|\s*(?:[a-zA-Z0-9_]{3,}[a-zA-Z0-9_.,-\\%\s'\"[\]()\{}]+)\s*)*)}}
    #       - Version 2: (2024-09-30):
    #         \${{\s*(?P<caller>(?P<caller_prefix>(?:[a-zA-Z_-]+\.)*)(?P<caller_last>[a-zA-Z0-9_\-.'\"(\)[\]{}]+))\s*(?P<post_filters>(?:\|\s*(?:[a-zA-Z0-9_]{3,}[a-zA-Z0-9_.,-\\%\s'\"[\]()\{}]+)\s*)*)}}
    #       - Version 3: (2024-10-05):
    #         \${{\s*(?P<caller>(?P<caller_prefix>(?:[a-zA-Z_-]+\??\.)*)(?P<caller_last>[a-zA-Z0-9_\-.'\"(\)[\]{}]+\??))\s*(?P<post_filters>(?:\|\s*(?:[a-zA-Z0-9_]{3,}[a-zA-Z0-9_.,-\\%\s'\"[\]()\{}]+)\s*)*)}}
    #
    #   Examples:
    #       - ${{ params.data_dt }}
    #       - ${{ params.source.table }}
    #       - ${{ params.datetime | fmt('%Y-%m-%d') }}
    #       - ${{ params.source?.schema }}
    #
    __re_caller: str = r"""
        \$
        {{
            \s*
            (?P<caller>
                (?P<caller_prefix>(?:[a-zA-Z_-]+\??\.)*)
                (?P<caller_last>[a-zA-Z0-9_\-.'\"(\)[\]{}]+\??)
            )
            \s*
            (?P<post_filters>
                (?:
                    \|\s*
                    (?:
                        [a-zA-Z0-9_]{3,}
                        [a-zA-Z0-9_.,-\\%\s'\"[\]()\{}]*
                    )\s*
                )*
            )
        }}
    """
    RE_CALLER: Pattern = re.compile(
        __re_caller, MULTILINE | IGNORECASE | UNICODE | VERBOSE
    )

    # NOTE:
    #   Regular expression:
    #       - Version 1:
    #         ^(?P<path>[^/@]+)/(?P<func>[^@]+)@(?P<tag>.+)$
    #
    #   Examples:
    #       - tasks/function@dummy
    #
    __re_task_fmt: str = r"""
        ^
            (?P<path>[^/@]+)
            /
            (?P<func>[^@]+)
            @
            (?P<tag>.+)
        $
    """
    RE_TASK_FMT: Pattern = re.compile(
        __re_task_fmt, MULTILINE | IGNORECASE | UNICODE | VERBOSE
    )

    @classmethod
    def finditer_caller(cls, value) -> Iterator[CallerRe]:
        """Generate CallerRe object that create from matching object that
        extract with re.finditer function.

        :rtype: Iterator[CallerRe]
        """
        for found in cls.RE_CALLER.finditer(value):
            yield CallerRe.from_regex(found)
