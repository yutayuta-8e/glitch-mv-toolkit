"""Glyph coverage check without fontTools: compare a char's rendering to .notdef."""
import functools
import numpy as np
from PIL import ImageFont

SIZE = 64


@functools.lru_cache(maxsize=None)
def _font(path):
    return ImageFont.truetype(path, SIZE)


def _mask(font, ch):
    m = font.getmask(ch)
    return np.array(m, dtype=np.uint8).reshape(m.size[1], m.size[0]) if m.size[0] and m.size[1] else np.zeros((0, 0), np.uint8)


@functools.lru_cache(maxsize=None)
def _notdef(path):
    f = _font(path)
    return [_mask(f, ''), _mask(f, '\U000f0001')]


@functools.lru_cache(maxsize=None)
def has_char(path, ch):
    if ch.isspace():
        return True
    f = _font(path)
    m = _mask(f, ch)
    if m.size == 0 or m.max() == 0:
        return False
    for nd in _notdef(path):
        if nd.shape == m.shape and np.array_equal(nd, m):
            return False
    return True


def has_glyphs(path, text):
    return all(has_char(path, c) for c in text)


def missing(path, text):
    return [c for c in text if not has_char(path, c)]
