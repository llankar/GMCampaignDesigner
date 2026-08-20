"""Conversions between decoded video frames and Pillow images."""

from PIL import Image


def decoded_frame_to_image(frame: object) -> Image.Image:
    """Copy a packed RGBA PyAV frame while honouring its padded row stride."""
    rgba = frame.reformat(format="rgba")
    plane = rgba.planes[0]
    return Image.frombytes(
        "RGBA",
        (rgba.width, rgba.height),
        bytes(plane),
        "raw",
        "RGBA",
        plane.line_size,
        1,
    )


def fit_frame(image: Image.Image, max_size: int) -> Image.Image:
    frame = image.convert("RGBA")
    if max(frame.size) > max_size:
        frame.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return frame


def has_transparency(image: Image.Image) -> bool:
    """Return whether an RGBA image contains at least one non-opaque pixel."""
    return image.getchannel("A").getextrema()[0] < 255
