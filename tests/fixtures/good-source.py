#!/usr/bin/env python3
"""Read a record file and return its rows.

The reader holds the file open for the length of the call. A caller that
needs the rows twice should keep the returned list.
"""

import csv


def load(path):
    # csv.reader wants a handle, not a path. It also needs an empty newline
    # argument, so a quoted field spanning two lines survives the read.
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def save(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
