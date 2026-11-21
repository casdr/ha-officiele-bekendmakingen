"""Tests for the areas of notices."""

from __future__ import annotations

import pytest

from custom_components.officiele_bekendmakingen.geometry import parse_area

# A square of about 137 by 222 m in Arnhem.
SQUARE = "POLYGON((5.900 51.980,5.902 51.980,5.902 51.982,5.900 51.982,5.900 51.980))"


def test_point() -> None:
    """A point is written as latitude,longitude."""
    area = parse_area("51.984068,5.9041452")

    assert area is not None
    assert area.center == (51.984068, 5.9041452)
    assert area.distance_to(51.984068, 5.9041452) == 0
    # 0.001 degree of latitude is 111 m.
    assert area.distance_to(51.985068, 5.9041452) == pytest.approx(111.2, abs=0.1)


def test_polygon() -> None:
    """A polygon is written as longitude latitude pairs, and has an inside."""
    area = parse_area(SQUARE)

    assert area is not None
    assert area.center == pytest.approx((51.9808, 5.9008))
    assert area.distance_to(51.981, 5.901) == 0
    # 0.001 degree north of the northern edge.
    assert area.distance_to(51.983, 5.901) == pytest.approx(111.2, abs=0.1)
    # North-east of the corner: the distance to that corner.
    assert area.distance_to(51.983, 5.903) == pytest.approx(130.6, abs=0.5)


def test_polygon_with_hole() -> None:
    """A position in a hole of a polygon is outside it."""
    area = parse_area(
        "POLYGON((5.90 51.98,5.91 51.98,5.91 51.99,5.90 51.99,5.90 51.98),"
        "(5.904 51.984,5.906 51.984,5.906 51.986,5.904 51.986,5.904 51.984))"
    )

    assert area is not None
    assert area.distance_to(51.982, 5.902) == 0
    assert area.distance_to(51.985, 5.905) > 50


def test_line() -> None:
    """A line has no inside, the distance is to the nearest part of it."""
    area = parse_area("LINESTRING(5.900 51.980,5.902 51.980)")

    assert area is not None
    assert area.distance_to(51.981, 5.901) == pytest.approx(111.2, abs=0.1)
    assert area.distance_to(51.980, 5.901) == pytest.approx(0, abs=0.01)


@pytest.mark.parametrize("text", ["", "unknown", "POLYGON(())", "51.98", "a,b"])
def test_invalid(text: str) -> None:
    """An area that is not understood is left out."""
    assert parse_area(text) is None
