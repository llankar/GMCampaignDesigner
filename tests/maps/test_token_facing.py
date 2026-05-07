"""Tests for token facing geometry."""

import math

from modules.maps.utils.token_facing import (
    facing_angle_from_points,
    facing_arrow_points,
    facing_arrowhead_points,
    facing_vector,
    normalize_facing_angle,
    token_center,
)


def test_normalize_facing_angle_wraps_and_defaults() -> None:
    """Facing angles are stored as finite degrees in [0, 360)."""
    assert normalize_facing_angle(725) == 5
    assert normalize_facing_angle(-90) == 270
    assert normalize_facing_angle("bad", default=45) == 45


def test_facing_angle_from_points_uses_canvas_orientation() -> None:
    """Canvas coordinates grow downward, so 90 degrees points down."""
    assert facing_angle_from_points(10, 10, 20, 10) == 0
    assert facing_angle_from_points(10, 10, 10, 20) == 90
    assert facing_angle_from_points(10, 10, 0, 10) == 180
    assert facing_angle_from_points(10, 10, 10, 0) == 270


def test_facing_vector_matches_cardinal_directions() -> None:
    """Facing vectors should align with cardinal canvas directions."""
    assert facing_vector(0) == (1.0, 0.0)
    down_x, down_y = facing_vector(90)
    assert math.isclose(down_x, 0.0, abs_tol=1e-9)
    assert math.isclose(down_y, 1.0, abs_tol=1e-9)


def test_facing_arrow_points_include_pan_zoom_and_offset() -> None:
    """Arrow endpoints should be returned in screen/render coordinates."""
    assert token_center((10, 20), 40) == (30, 40)
    start_x, start_y, end_x, end_y = facing_arrow_points(
        (10, 20),
        40,
        0,
        zoom=2,
        pan_x=5,
        pan_y=7,
        offset_x=3,
        offset_y=4,
    )
    assert (start_x, start_y) == (68, 83)
    assert math.isclose(end_x, 114.8)
    assert end_y == 83


def test_facing_arrowhead_points_orient_triangle_tip() -> None:
    """The facing handle is a triangle with its tip in the facing direction."""
    right = facing_arrowhead_points(100, 50, 0, length=20, width=10)
    assert right == (100.0, 50.0, 80.0, 55.0, 80.0, 45.0)

    down = facing_arrowhead_points(100, 50, 90, length=20, width=10)
    assert down[0:2] == (100.0, 50.0)
    assert math.isclose(down[3], 30.0, abs_tol=1e-9)
    assert math.isclose(down[5], 30.0, abs_tol=1e-9)
