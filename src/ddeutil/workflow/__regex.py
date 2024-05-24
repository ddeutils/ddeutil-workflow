# -------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# --------------------------------------------------------------------------
import re
from re import (
    IGNORECASE,
    MULTILINE,
    UNICODE,
    VERBOSE,
    Pattern,
)


class RegexConf:
    """Regular expression config."""

    # NOTE: Search caller
    __re_caller: str = r"""
        \$
        {{
            \s*(?P<caller>
                [a-zA-Z0-9_.\s'\"\[\]\(\)\-\{}]+?
            )\s*
        }}
    """
    RE_CALLER: Pattern = re.compile(
        __re_caller, MULTILINE | IGNORECASE | UNICODE | VERBOSE
    )

    # NOTE: Search task
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
