"""The area a notice is about, and how far that is from a position.

A notice marks its area in WGS84 as WKT with "longitude latitude" pairs, such as
``POLYGON((5.91 51.98,...))`` or ``LINESTRING(...)``, or as a single
``latitude,longitude`` point.
"""

from __future__ import annotations

import dataclasses
import math
import re
from itertools import pairwise
from typing import Final

_EARTH_RADIUS: Final = 6_371_000.0
_RING: Final = re.compile(r"\(([^()]+)\)")

type Position = tuple[float, float]
"""A latitude and a longitude, in degrees."""


@dataclasses.dataclass(frozen=True, slots=True)
class Area:
    """Polygons, lines or one point."""

    rings: tuple[tuple[Position, ...], ...]
    closed: bool

    @property
    def center(self) -> Position:
        """The average of the corners, good enough to put a pin on a map."""
        positions = [position for ring in self.rings for position in ring]
        return (
            sum(latitude for latitude, _ in positions) / len(positions),
            sum(longitude for _, longitude in positions) / len(positions),
        )

    def distance_to(self, latitude: float, longitude: float) -> float:
        """Return the metres from a position to the area, 0 inside a polygon."""
        scale = math.cos(math.radians(latitude))
        # Metres east and north of the position, which itself is at (0, 0).
        rings = [
            [
                (
                    math.radians(ring_longitude - longitude) * scale * _EARTH_RADIUS,
                    math.radians(ring_latitude - latitude) * _EARTH_RADIUS,
                )
                for ring_latitude, ring_longitude in ring
            ]
            for ring in self.rings
        ]
        if self.closed:
            # Even-odd rule over all rings, so holes and multipolygons work.
            crossings = sum(
                _crosses_east(start, end)
                for ring in rings
                for start, end in _edges(ring)
            )
            if crossings % 2:
                return 0.0
        return min(
            _distance_to_segment(start, end)
            for ring in rings
            for start, end in _segments(ring)
        )


def parse_area(text: str) -> Area | None:
    """Parse the area of a notice, None when it is not understood."""
    text = text.strip()
    try:
        if not text[:1].isalpha():
            latitude, longitude = (float(part) for part in text.split(","))
            return Area((((latitude, longitude),),), closed=False)
        rings = tuple(
            tuple(_parse_pair(pair) for pair in ring.split(","))
            for ring in _RING.findall(text)
        )
    except ValueError:
        return None
    if not rings:
        return None
    return Area(rings, closed="POLYGON" in text.upper())


def _parse_pair(pair: str) -> Position:
    longitude, latitude = (float(part) for part in pair.split()[:2])
    return latitude, longitude


type _Point = tuple[float, float]


def _segments(ring: list[_Point]) -> list[tuple[_Point, _Point]]:
    """Return the segments of a ring, or the ring itself when it is one point."""
    if len(ring) == 1:
        return [(ring[0], ring[0])]
    return list(pairwise(ring))


def _edges(ring: list[_Point]) -> list[tuple[_Point, _Point]]:
    """Return the edges of a polygon ring, closing it when the data did not."""
    edges = list(pairwise(ring))
    if ring[0] != ring[-1]:
        edges.append((ring[-1], ring[0]))
    return edges


def _distance_to_segment(start: _Point, end: _Point) -> float:
    """Return the distance from (0, 0) to a segment."""
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    length = delta_x * delta_x + delta_y * delta_y
    if length == 0:
        return math.hypot(*start)
    along = -(start[0] * delta_x + start[1] * delta_y) / length
    along = max(0.0, min(1.0, along))
    return math.hypot(start[0] + along * delta_x, start[1] + along * delta_y)


def _crosses_east(start: _Point, end: _Point) -> bool:
    """Return whether a ray from (0, 0) to the east crosses a segment."""
    if (start[1] > 0) == (end[1] > 0):
        return False
    return start[0] - start[1] * (end[0] - start[0]) / (end[1] - start[1]) > 0
