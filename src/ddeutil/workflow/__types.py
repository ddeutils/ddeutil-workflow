# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import re
from re import (
    IGNORECASE,
    MULTILINE,
    UNICODE,
    VERBOSE,
    Pattern,
)
from typing import Any, Union

TupleStr = tuple[str, ...]
DictData = dict[str, Any]
DictStr = dict[str, str]
Matrix = dict[str, Union[list[str], list[int]]]
MatrixInclude = list[dict[str, Union[str, int]]]
MatrixExclude = list[dict[str, Union[str, int]]]


class Re:
    """Regular expression config for this package."""

    # NOTE:
    #   Regular expression:
    #   \${{\s*(?P<caller>[a-zA-Z0-9_.\s'\"\[\]\(\)\-\{}]+?)\s*(?P<post_filters>(?:\|\s*(?:[a-zA-Z0-9_]{3,}[a-zA-Z0-9_.,-\\%\s'\"[\]()\{}]+)\s*)*)}}
    #
    #   Examples:
    #       - ${{ params.asat_dt }}
    #       - ${{ params.source.table }}
    #
    __re_caller: str = r"""
        \$
        {{
            \s*
            (?P<caller>
                [a-zA-Z0-9_.\s'\"\[\]\(\)\-\{}]+?
            )\s*
            (?P<post_filters>
                (?:
                    \|\s*
                    (?:[a-zA-Z0-9_]{3,}[a-zA-Z0-9_.,-\\%\s'\"[\]()\{}]*)
                    \s*
                )*
            )
        }}
    """
    RE_CALLER: Pattern = re.compile(
        __re_caller, MULTILINE | IGNORECASE | UNICODE | VERBOSE
    )

    # NOTE:
    #   Regular expression:
    #   ^(?P<path>[^/@]+)/(?P<func>[^@]+)@(?P<tag>.+)$
    #
    #   Examples:
    #       - tasks/function@dummy
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
