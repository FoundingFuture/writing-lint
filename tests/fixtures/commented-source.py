#!/usr/bin/env python3
"""This module provides a comprehensive and robust helper.

It is designed to facilitate the seamless processing of records, and it
leverages a powerful abstraction so that you can effortlessly extend it
later on without having to rewrite any of the calling code at all.
"""

# =========================================================
# Record handling
# =========================================================

import os


def load(path):
    # This function reads the file and returns the rows.
    # Note that the caller should ensure the path exists.
    # TODO fix the encoding
    # for row in rows:
    #     print(row)
    return open(path).read()


def save(path, data):
    """Utilize the writer to persist data.

    IMPORTANT NOTE HERE: the caller must close it.
    """
    # In order to keep it simple, we just write the whole thing at once...
    with open(path, "w") as handle:
        handle.write(data)
