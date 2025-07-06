"""
Test slack access.
"""

import pytest
import sys
import os.path
from orca_agent.slack_client import chunkify


def test_chunkify_basic():
    s = "Line 1\nLine 2\nLine 3\n"
    chunks = list(chunkify(s, 10))
    assert chunks == ["Line 1\n", "Line 2\n", "Line 3\n"]


def test_chunkify_long_line():
    s = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    chunks = list(chunkify(s, 10))
    print(chunks)
    assert all(len(chunk) <= 10 for chunk in chunks)
    assert ''.join(chunks) == s


def test_chunkify_mixed_lines():
    s = "Short\n" + ("B" * 15) + "\nEnd\n"
    chunks = list(chunkify(s, 10))
    assert any("Short" in chunk for chunk in chunks)
    assert any("End" in chunk for chunk in chunks)
    assert ''.join(chunks).replace('\n', '').startswith('ShortB')


def test_chunkify_empty():
    s = ""
    chunks = list(chunkify(s, 10))
    assert chunks == []


def test_chunkify_exact_chunk():
    s = "1234567890"
    chunks = list(chunkify(s, 10))
    assert chunks == ["1234567890"]


