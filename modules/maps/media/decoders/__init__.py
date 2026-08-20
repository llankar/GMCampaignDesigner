"""Codec decoders used by map media, independent from Tkinter views."""

from .errors import MediaDecodeError
from .pyav import VideoDecoder

__all__ = ["MediaDecodeError", "VideoDecoder"]
