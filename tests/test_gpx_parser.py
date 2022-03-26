from pathlib import Path
from math import isclose

from parsers.gpx import GPXActivity
from parsers.gpx import calculate_distane2d


GPX_EXAMPLE_FILE = Path('tests') / 'example.gpx'
GPX_EXAMPLE_CONTENTS = GPX_EXAMPLE_FILE.read_text()


_gpx_activity = None


def create_gpx_activity() -> GPXActivity:
    # pythonic singleton
    global _gpx_activity
    if not _gpx_activity:
        _gpx_activity = GPXActivity.fromstring(GPX_EXAMPLE_CONTENTS)
    return _gpx_activity


def test_gpx_activity_created() -> None:
    create_gpx_activity()


def test_gpx_activity_gives_activity_name() -> None:
    activity = create_gpx_activity()
    assert activity.name == 'Сто!'


def test_gpx_activity_gives_activity_start_time() -> None:
    activity = create_gpx_activity()
    assert activity.start_time == '2020-06-24T05:36:31Z'


def test_gpx_activity_gives_activity_finish_time() -> None:
    activity = create_gpx_activity()
    assert activity.finish_time == '2020-06-24T10:18:16Z'


def test_gpx_activity_gives_activity_elevation() -> None:
    activity = create_gpx_activity()
    elevation = activity.elevation
    assert elevation
    assert 103.6 in elevation
    assert 122.0 in elevation


def test_gpx_activity_gives_activity_heart_rate() -> None:
    activity = create_gpx_activity()
    heart_rate = activity.heart_rate
    assert heart_rate
    for i in range(85, 160):
        assert i in heart_rate


def test_gpx_activity_gives_activity_power() -> None:
    activity = create_gpx_activity()
    power = activity.power
    assert power
    for i in range(120, 250):
        assert i in power
    assert 0 in power
    assert None in power


def test_gpx_activity_gives_activity_temperature() -> None:
    activity = create_gpx_activity()
    temperature = activity.temperature
    assert temperature
    for i in range(25, 31):
        assert i in temperature


def test_gpx_activity_gives_activity_cadence() -> None:
    activity = create_gpx_activity()
    cadence = activity.cadence
    assert cadence
    assert 40 in cadence
    assert 80 in cadence
    assert 90 in cadence


def test_calculate_distance_gives_correct_distance() -> None:
    lat1, lon1 = 55.879432, 37.612599
    lat2, lon2 = 55.869933, 37.480046
    expected = 8.336 * 1000
    calculated = calculate_distane2d(lat1, lon1, lat2, lon2)
    assert isclose(calculated, expected, rel_tol=0.01)


def test_gpx_activity_gives_activity_distance() -> None:
    activity = create_gpx_activity()
    assert isclose(activity.distance, 101.51 * 1000, rel_tol=0.01)
