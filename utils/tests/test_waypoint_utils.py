"""
TODO(bootcamper): write the tests for ``src/waypoint_utils.py`` in here.

The example below covers files that parse fine: with and without ``home``,
and files with comments and blank lines in them. The rest is yours:

- Bad data: a file whose top level isn't a mapping, waypoints missing
  ``lat``, ``lon``, or ``alt``, values that aren't numbers, YAML that
  doesn't parse, and a file that isn't there.
- Out of range: latitudes past +/-90 and longitudes past +/-180 get
  rejected.
- Nothing to work with: an empty file, an empty ``waypoints`` list, and
  ``sort_clockwise_sweep`` given a list of 0 or 1 waypoints.
- ``east_north_coordinate_offset_m``: offsets you worked out yourself,
  compared with ``pytest.approx``. Never use ``==`` on meters.
- Ordering: with no ``home``, ``sort_clockwise_sweep`` goes clockwise
  starting from north.
- With a ``home``: the order starts in home's direction instead, and goes
  back to starting at north if home is right on top of the centroid.
- Two waypoints in the same direction: the closer one comes first.
- Parsing gives you frozen ``Coordinate`` objects that can't be changed.

Graded by ``warg run utils grade-tests``: pass on the real code, 90% branch
coverage, and fail on every broken copy in ``grader/mutants/``.
"""


import dataclasses
import math

import pytest

from src.types import Coordinate
from src.waypoint_utils import (
    east_north_coordinate_offset_m,
    parse_waypoints_file,
    sort_clockwise_sweep,
)

# The helper and the test below are given to you.


def write_to_tmp_waypoints_file(tmp_path, text):
    """Write ``text`` to a YAML file and hand back its path.

    ``tmp_path`` is a pytest fixture: a fresh empty directory per test.
    """
    path = tmp_path / "waypoints.yaml"
    path.write_text(text)
    return path


# One test, three files. ``parametrize`` runs the test body once per
# ``(text, expected)`` pair, and ``ids`` names each run so a failure tells you
# which file broke.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            """
            home: {lat: 1, lon: 2, alt: 3}
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
        (
            """
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
              - {lat: 7, lon: 8, alt: 9}
            """,
            (None, [Coordinate(4, 5, 6), Coordinate(7, 8, 9)]),
        ),
        (
            """
            # a lap

            home: {lat: 1, lon: 2, alt: 3}

            waypoints:
              # first leg
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
    ],
    ids=["home-and-waypoints", "no-home", "comments-and-blank-lines"],
)
def test_parse_waypoints_file_success(tmp_path, text, expected):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == expected


def test_parse_accepts_str_path(tmp_path):
    path = write_to_tmp_waypoints_file(
        tmp_path, "waypoints:\n  - {lat: 1, lon: 2, alt: 3}\n"
    )
    assert parse_waypoints_file(str(path)) == (None, [Coordinate(1, 2, 3)])
 
 
def test_parse_keeps_decimal_values_and_waypoint_order(tmp_path):
    text = """
    home: {lat: 43.47152, lon: -80.5414, alt: 15}
    waypoints:
      - {lat: 43.47179, lon: -80.541524, alt: 15}
      - {lat: 43.4719, lon: -80.5416, alt: 20.5}
      - {lat: 43.4716, lon: -80.5417, alt: 10}
    """
    home, waypoints = parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))
    assert home == Coordinate(43.47152, -80.5414, 15.0)
    assert waypoints == [
        Coordinate(43.47179, -80.541524, 15.0),
        Coordinate(43.4719, -80.5416, 20.5),
        Coordinate(43.4716, -80.5417, 10.0),
    ]
 
 
def test_parse_converts_values_to_float(tmp_path):
    text = "home: {lat: 1, lon: 2, alt: 3}\nwaypoints:\n  - {lat: 4, lon: 5, alt: 6}\n"
    home, waypoints = parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))
    for coordinate in (home, waypoints[0]):
        assert isinstance(coordinate.lat, float)
        assert isinstance(coordinate.lon, float)
        assert isinstance(coordinate.alt, float)
 
 
def test_parse_accepts_numeric_strings(tmp_path):
    text = "waypoints:\n  - {lat: '4.5', lon: '5', alt: '6'}\n"
    _, waypoints = parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))
    assert waypoints == [Coordinate(4.5, 5.0, 6.0)]
    assert isinstance(waypoints[0].lat, float)
 
 
def test_parse_does_not_range_check_altitude(tmp_path):
    text = "waypoints:\n  - {lat: 1, lon: 2, alt: -500}\n  - {lat: 1, lon: 2, alt: 99999}\n"
    _, waypoints = parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))
    assert [w.alt for w in waypoints] == [-500.0, 99999.0]
 
 
@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90, 0), (-90, 0), (0, 180), (0, -180), (90, 180), (-90, -180)],
    ids=["lat-max", "lat-min", "lon-max", "lon-min", "both-max", "both-min"],
)
def test_parse_accepts_boundary_coordinates(tmp_path, lat, lon):
    text = f"home: {{lat: {lat}, lon: {lon}, alt: 0}}\nwaypoints:\n  - {{lat: {lat}, lon: {lon}, alt: 0}}\n"
    home, waypoints = parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))
    assert home == Coordinate(lat, lon, 0)
    assert waypoints == [Coordinate(lat, lon, 0)]
 
 
def test_parsed_coordinates_are_frozen(tmp_path):
    text = "home: {lat: 1, lon: 2, alt: 3}\nwaypoints:\n  - {lat: 4, lon: 5, alt: 6}\n"
    home, waypoints = parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))
    with pytest.raises(dataclasses.FrozenInstanceError):
        home.lat = 50.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        waypoints[0].alt = 50.0
 
 
def test_coordinate_str():
    assert str(Coordinate(1.5, -2.5, 3.0)) == "(1.5, -2.5, 3.0)"
 
 
# parse_waypoints_file: empty / nothing to work with
 
 
@pytest.mark.parametrize(
    "text",
    ["", "\n\n", "# only a comment\n"],
    ids=["empty", "blank-lines", "comment-only"],
)
def test_parse_empty_file_gives_no_home_and_no_waypoints(tmp_path, text):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == (None, [])
 
 
def test_parse_empty_waypoints_list(tmp_path):
    path = write_to_tmp_waypoints_file(tmp_path, "waypoints: []\n")
    assert parse_waypoints_file(path) == (None, [])
 
 
def test_parse_null_waypoints(tmp_path):
    path = write_to_tmp_waypoints_file(tmp_path, "waypoints:\n")
    assert parse_waypoints_file(path) == (None, [])
 
 
def test_parse_home_only(tmp_path):
    path = write_to_tmp_waypoints_file(tmp_path, "home: {lat: 1, lon: 2, alt: 3}\n")
    assert parse_waypoints_file(path) == (Coordinate(1, 2, 3), [])
 
 
def test_parse_null_home_is_no_home(tmp_path):
    path = write_to_tmp_waypoints_file(
        tmp_path, "home:\nwaypoints:\n  - {lat: 1, lon: 2, alt: 3}\n"
    )
    assert parse_waypoints_file(path) == (None, [Coordinate(1, 2, 3)])
 
 
# parse_waypoints_file: bad data
 
 
def test_parse_missing_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        parse_waypoints_file(tmp_path / "does_not_exist.yaml")
 
 
def test_parse_invalid_yaml_raises_value_error(tmp_path):
    path = write_to_tmp_waypoints_file(tmp_path, "home: [unclosed\n")
    with pytest.raises(ValueError, match="invalid YAML") as excinfo:
        parse_waypoints_file(path)
    assert excinfo.value.__cause__ is not None
 
 
@pytest.mark.parametrize(
    "text",
    ["- 1\n- 2\n", "just a string\n", "42\n"],
    ids=["list", "string", "number"],
)
def test_parse_top_level_not_a_mapping(tmp_path, text):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match="expected a mapping"):
        parse_waypoints_file(path)
 
 
@pytest.mark.parametrize(
    "text",
    ["waypoints: 5\n", "waypoints: {lat: 1, lon: 2, alt: 3}\n", "waypoints: text\n"],
    ids=["number", "mapping", "string"],
)
def test_parse_waypoints_not_a_list(tmp_path, text):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match="'waypoints' must be a list"):
        parse_waypoints_file(path)
 
 
@pytest.mark.parametrize(
    "text",
    [
        "home: 5\n",
        "home: [1, 2, 3]\n",
        "home: text\n",
        "waypoints:\n  - 5\n",
        "waypoints:\n  - [1, 2, 3]\n",
        "waypoints:\n  - text\n",
    ],
    ids=[
        "home-number",
        "home-list",
        "home-string",
        "waypoint-number",
        "waypoint-list",
        "waypoint-string",
    ],
)
def test_parse_entry_not_a_mapping(tmp_path, text):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match="must be a mapping"):
        parse_waypoints_file(path)
 
 
@pytest.mark.parametrize("missing", ["lat", "lon", "alt"])
def test_parse_waypoint_missing_key(tmp_path, missing):
    entry = {"lat": 1, "lon": 2, "alt": 3}
    del entry[missing]
    body = ", ".join(f"{key}: {value}" for key, value in entry.items())
    path = write_to_tmp_waypoints_file(tmp_path, f"waypoints:\n  - {{{body}}}\n")
    with pytest.raises(ValueError, match=f"missing key.*{missing}"):
        parse_waypoints_file(path)
 
 
@pytest.mark.parametrize("missing", ["lat", "lon", "alt"])
def test_parse_home_missing_key(tmp_path, missing):
    entry = {"lat": 1, "lon": 2, "alt": 3}
    del entry[missing]
    body = ", ".join(f"{key}: {value}" for key, value in entry.items())
    path = write_to_tmp_waypoints_file(tmp_path, f"home: {{{body}}}\n")
    with pytest.raises(ValueError, match=f"home is missing key.*{missing}"):
        parse_waypoints_file(path)
 
 
def test_parse_missing_key_lists_every_missing_key(tmp_path):
    path = write_to_tmp_waypoints_file(tmp_path, "waypoints:\n  - {lat: 1}\n")
    with pytest.raises(ValueError, match="lon, alt"):
        parse_waypoints_file(path)
 
 
@pytest.mark.parametrize(
    "bad_entry",
    [
        "{lat: north, lon: 2, alt: 3}",
        "{lat: 1, lon: east, alt: 3}",
        "{lat: 1, lon: 2, alt: high}",
        "{lat: null, lon: 2, alt: 3}",
        "{lat: 1, lon: null, alt: 3}",
        "{lat: 1, lon: 2, alt: null}",
        "{lat: [1, 2], lon: 2, alt: 3}",
    ],
    ids=[
        "lat-text",
        "lon-text",
        "alt-text",
        "lat-null",
        "lon-null",
        "alt-null",
        "lat-list",
    ],
)
def test_parse_non_numeric_value(tmp_path, bad_entry):
    path = write_to_tmp_waypoints_file(tmp_path, f"waypoints:\n  - {bad_entry}\n")
    with pytest.raises(ValueError, match="non-numeric") as excinfo:
        parse_waypoints_file(path)
    assert excinfo.value.__cause__ is not None
 
 
def test_parse_non_numeric_home(tmp_path):
    path = write_to_tmp_waypoints_file(tmp_path, "home: {lat: x, lon: 2, alt: 3}\n")
    with pytest.raises(ValueError, match="home has a non-numeric"):
        parse_waypoints_file(path)
 
 
@pytest.mark.parametrize(
    "lat_lon",
    [
        (90.0001, 0),
        (-90.0001, 0),
        (0, 180.0001),
        (0, -180.0001),
        (91, 0),
        (-91, 0),
        (0, 181),
        (0, -181),
        (1000, 1000),
    ],
    ids=[
        "lat-just-over",
        "lat-just-under",
        "lon-just-over",
        "lon-just-under",
        "lat-91",
        "lat-minus-91",
        "lon-181",
        "lon-minus-181",
        "both-huge",
    ],
)
def test_parse_out_of_range_waypoint(tmp_path, lat_lon):
    lat, lon = lat_lon
    path = write_to_tmp_waypoints_file(
        tmp_path, f"waypoints:\n  - {{lat: {lat}, lon: {lon}, alt: 0}}\n"
    )
    with pytest.raises(ValueError, match="out of range"):
        parse_waypoints_file(path)
 
 
@pytest.mark.parametrize(
    "lat_lon",
    [(90.5, 0), (-90.5, 0), (0, 180.5), (0, -180.5)],
    ids=["lat-over", "lat-under", "lon-over", "lon-under"],
)
def test_parse_out_of_range_home(tmp_path, lat_lon):
    lat, lon = lat_lon
    path = write_to_tmp_waypoints_file(
        tmp_path, f"home: {{lat: {lat}, lon: {lon}, alt: 0}}\n"
    )
    with pytest.raises(ValueError, match="home latitude/longitude out of range"):
        parse_waypoints_file(path)
 
 
def test_parse_error_names_the_bad_waypoint_and_the_file(tmp_path):
    text = """
    waypoints:
      - {lat: 1, lon: 2, alt: 3}
      - {lat: 4, lon: 5}
    """
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match="waypoint 2") as excinfo:
        parse_waypoints_file(path)
    assert str(path) in str(excinfo.value)
 
 
def test_parse_first_waypoint_is_numbered_one(tmp_path):
    path = write_to_tmp_waypoints_file(tmp_path, "waypoints:\n  - {lat: 1}\n")
    with pytest.raises(ValueError, match="waypoint 1"):
        parse_waypoints_file(path)
 
 
def test_parse_one_bad_waypoint_rejects_the_whole_file(tmp_path):
    text = """
    waypoints:
      - {lat: 1, lon: 2, alt: 3}
      - {lat: 100, lon: 5, alt: 6}
      - {lat: 7, lon: 8, alt: 9}
    """
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match="waypoint 2"):
        parse_waypoints_file(path)
 
 
# east_north_coordinate_offset_m

 
METERS_PER_DEGREE = 111195.08  # 6371008.8 * pi / 180
 
 
def test_offset_to_same_point_is_zero():
    east, north = east_north_coordinate_offset_m(43.47, -80.54, 43.47, -80.54)
    assert east == pytest.approx(0.0, abs=1e-6)
    assert north == pytest.approx(0.0, abs=1e-6)
 
 
def test_offset_one_degree_east_at_equator():
    east, north = east_north_coordinate_offset_m(0, 0, 0, 1)
    assert east == pytest.approx(METERS_PER_DEGREE, abs=0.01)
    assert north == pytest.approx(0.0, abs=1e-6)
 
 
def test_offset_one_degree_north():
    east, north = east_north_coordinate_offset_m(0, 0, 1, 0)
    assert east == pytest.approx(0.0, abs=1e-6)
    assert north == pytest.approx(METERS_PER_DEGREE, abs=0.01)
 
 
def test_offset_west_and_south_are_negative():
    east, north = east_north_coordinate_offset_m(0, 0, -1, -1)
    assert east < 0
    assert north < 0
 
 
def test_offset_east_shrinks_with_latitude():
    # At 60 degrees latitude a degree of longitude is half as wide.
    east, north = east_north_coordinate_offset_m(60, 0, 60, 1)
    assert east == pytest.approx(55597.54, abs=0.01)
    assert north == pytest.approx(0.0, abs=1e-6)
 
 
def test_offset_uses_the_average_of_the_two_latitudes():
    # Mean latitude is 30 degrees, so cos is 0.866.
    east, north = east_north_coordinate_offset_m(0, 0, 60, 1)
    assert east == pytest.approx(96297.76, abs=0.01)
    assert north == pytest.approx(6671704.81, abs=0.01)
 
 
def test_offset_reversing_the_points_flips_the_sign():
    east, north = east_north_coordinate_offset_m(60, 1, 0, 0)
    assert east == pytest.approx(-96297.76, abs=0.01)
    assert north == pytest.approx(-6671704.81, abs=0.01)
 
 
def test_offset_argument_order_is_from_lat_lon_to_lat_lon():
    # Different lat/lon deltas, so mixed-up arguments give different answers.
    east, north = east_north_coordinate_offset_m(10, 20, 10, 19)
    assert east == pytest.approx(-109505.78, abs=0.01)
    assert north == pytest.approx(0.0, abs=1e-6)
 
 
def test_offset_small_real_world_distance():
    east, north = east_north_coordinate_offset_m(
        43.47152, -80.5414, 43.47179, -80.541524
    )
    assert east == pytest.approx(-10.006, abs=0.01)
    assert north == pytest.approx(30.023, abs=0.01)
 
 

# sort_clockwise_sweep
 
# Four waypoints due north, east, south, and west of (0, 0), the centroid.
NORTH = Coordinate(0.001, 0.0, 10.0)
EAST = Coordinate(0.0, 0.001, 11.0)
SOUTH = Coordinate(-0.001, 0.0, 12.0)
WEST = Coordinate(0.0, -0.001, 13.0)
 
 
def test_sort_empty_list():
    assert sort_clockwise_sweep([]) == []
 
 
def test_sort_single_waypoint():
    waypoint = Coordinate(1, 2, 3)
    assert sort_clockwise_sweep([waypoint]) == [waypoint]
 
 
def test_sort_single_waypoint_ignores_home():
    waypoint = Coordinate(1, 2, 3)
    assert sort_clockwise_sweep([waypoint], home=Coordinate(50, 50, 0)) == [waypoint]
 
 
def test_sort_returns_a_new_list():
    waypoints = [NORTH]
    assert sort_clockwise_sweep(waypoints) is not waypoints
    assert sort_clockwise_sweep([]) is not waypoints
 
 
def test_sort_does_not_change_the_input_list():
    waypoints = [WEST, NORTH, SOUTH, EAST]
    sort_clockwise_sweep(waypoints)
    assert waypoints == [WEST, NORTH, SOUTH, EAST]
 
 
@pytest.mark.parametrize(
    "shuffled",
    [
        [NORTH, EAST, SOUTH, WEST],
        [WEST, SOUTH, EAST, NORTH],
        [SOUTH, NORTH, WEST, EAST],
        [EAST, WEST, NORTH, SOUTH],
    ],
    ids=["in-order", "reversed", "shuffled-1", "shuffled-2"],
)
def test_sort_without_home_goes_clockwise_from_north(shuffled):
    assert sort_clockwise_sweep(shuffled) == [NORTH, EAST, SOUTH, WEST]
 
 
def test_sort_without_home_with_diagonal_points():
    north_east = Coordinate(0.001, 0.001, 0.0)
    south_east = Coordinate(-0.001, 0.001, 0.0)
    south_west = Coordinate(-0.001, -0.001, 0.0)
    north_west = Coordinate(0.001, -0.001, 0.0)
    shuffled = [south_west, north_east, north_west, south_east]
    assert sort_clockwise_sweep(shuffled) == [
        north_east,
        south_east,
        south_west,
        north_west,
    ]
 
 
def test_sort_two_waypoints():
    assert sort_clockwise_sweep([SOUTH, NORTH]) == [NORTH, SOUTH]
 
 
def test_sort_with_home_starts_in_homes_direction_east():
    home = Coordinate(0.0, 0.01, 0.0)
    assert sort_clockwise_sweep([NORTH, SOUTH, WEST, EAST], home) == [
        EAST,
        SOUTH,
        WEST,
        NORTH,
    ]
 
 
def test_sort_with_home_starts_in_homes_direction_south():
    home = Coordinate(-0.01, 0.0, 0.0)
    assert sort_clockwise_sweep([NORTH, EAST, WEST, SOUTH], home) == [
        SOUTH,
        WEST,
        NORTH,
        EAST,
    ]
 
 
def test_sort_with_home_starts_in_homes_direction_west():
    home = Coordinate(0.0, -0.01, 0.0)
    assert sort_clockwise_sweep([NORTH, EAST, SOUTH, WEST], home) == [
        WEST,
        NORTH,
        EAST,
        SOUTH,
    ]
 
 
def test_sort_with_home_north_matches_no_home():
    home = Coordinate(0.01, 0.0, 0.0)
    assert sort_clockwise_sweep([EAST, WEST, NORTH, SOUTH], home) == [
        NORTH,
        EAST,
        SOUTH,
        WEST,
    ]
 
 
def test_sort_with_home_between_waypoints_starts_at_the_next_one_clockwise():
    # Home is north-east of the centroid, so the sweep starts at east.
    home = Coordinate(0.01, 0.01, 0.0)
    assert sort_clockwise_sweep([NORTH, EAST, SOUTH, WEST], home) == [
        EAST,
        SOUTH,
        WEST,
        NORTH,
    ]
 
 
def test_sort_with_home_just_clockwise_of_north_puts_north_last():
    # Home is a hair east of north, so north is a hair counter-clockwise of
    # the start and comes last.
    home = Coordinate(0.01, 0.0001, 0.0)
    assert sort_clockwise_sweep([NORTH, EAST, SOUTH, WEST], home) == [
        EAST,
        SOUTH,
        WEST,
        NORTH,
    ]
 
 
def test_sort_with_home_on_the_centroid_starts_at_north():
    home = Coordinate(0.0, 0.0, 0.0)
    assert sort_clockwise_sweep([WEST, SOUTH, EAST, NORTH], home) == [
        NORTH,
        EAST,
        SOUTH,
        WEST,
    ]
 
 
def test_sort_with_home_almost_on_the_centroid_still_uses_its_direction():
    # About 1 cm east of the centroid: close, but not on top of it.
    home = Coordinate(0.0, 1e-7, 0.0)
    assert sort_clockwise_sweep([NORTH, EAST, SOUTH, WEST], home) == [
        EAST,
        SOUTH,
        WEST,
        NORTH,
    ]
 
 
def test_sort_home_is_not_part_of_the_result():
    home = Coordinate(0.0, 0.01, 0.0)
    assert home not in sort_clockwise_sweep([NORTH, EAST, SOUTH, WEST], home)
 
 
def test_sort_same_direction_closer_waypoint_comes_first():
    near = Coordinate(0.001, 0.0, 0.0)
    far = Coordinate(0.002, 0.0, 0.0)
    south = Coordinate(-0.003, 0.0, 0.0)
    assert sort_clockwise_sweep([far, south, near]) == [near, far, south]
    assert sort_clockwise_sweep([near, far, south]) == [near, far, south]
    assert sort_clockwise_sweep([south, far, near]) == [near, far, south]
 
 
def test_sort_same_direction_closer_first_when_not_at_north():
    near = Coordinate(0.0, 0.001, 0.0)
    far = Coordinate(0.0, 0.002, 0.0)
    west = Coordinate(0.0, -0.003, 0.0)
    assert sort_clockwise_sweep([west, far, near]) == [near, far, west]
 
 
def test_sort_same_direction_with_home():
    near = Coordinate(0.001, 0.0, 0.0)
    far = Coordinate(0.002, 0.0, 0.0)
    south = Coordinate(-0.003, 0.0, 0.0)
    home = Coordinate(-0.01, 0.0, 0.0)
    # Start at south, then wrap around to north: near before far.
    assert sort_clockwise_sweep([far, near, south], home) == [south, near, far]
 
 
def test_sort_uses_the_centroid_not_the_first_waypoint():
    # Centroid is (0.5, 0.5): the points are in the four corners around it.
    south_west = Coordinate(0.0, 0.0, 0.0)
    north_west = Coordinate(1.0, 0.0, 0.0)
    north_east = Coordinate(1.0, 1.0, 0.0)
    south_east = Coordinate(0.0, 1.0, 0.0)
    shuffled = [south_east, south_west, north_east, north_west]
    assert sort_clockwise_sweep(shuffled) == [
        north_east,
        south_east,
        south_west,
        north_west,
    ]
 
 
def test_sort_works_with_the_shape_of_a_real_lap():
    home = Coordinate(43.47152, -80.5414, 15.0)
    top = Coordinate(43.4719, -80.5414, 15.0)
    right = Coordinate(43.4715, -80.5410, 15.0)
    bottom = Coordinate(43.4711, -80.5414, 15.0)
    left = Coordinate(43.4715, -80.5418, 15.0)
    result = sort_clockwise_sweep([left, bottom, top, right], home)
    # Home sits at the centre-ish, slightly north of the centroid's row, so the
    # sweep is still a clockwise cycle through all four.
    assert sorted(result, key=lambda c: (c.lat, c.lon)) == sorted(
        [top, right, bottom, left], key=lambda c: (c.lat, c.lon)
    )
    ring = result + result
    start = ring.index(top)
    assert ring[start : start + 4] == [top, right, bottom, left]
 
 
def test_sort_bearing_math_is_consistent_with_the_offset_helper():
    # Points every 45 degrees around the centroid sort in compass order.
    radius = 0.001
    compass = [
        Coordinate(
            radius * math.cos(math.radians(deg)),
            radius * math.sin(math.radians(deg)),
            0.0,
        )
        for deg in range(0, 360, 45)
    ]
    shuffled = [compass[i] for i in (5, 2, 7, 0, 3, 6, 1, 4)]
    assert sort_clockwise_sweep(shuffled) == compass
 
