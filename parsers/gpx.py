from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from math import atan2
from math import cos
from math import isclose
from math import radians
from math import sin
from math import sqrt
from pathlib import Path
from statistics import mean
from statistics import median
from typing import Any
from typing import Optional
from typing import Union
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import fromstring
from xml.etree.ElementTree import parse

from numba import jit  # type: ignore


@jit(nopython=True, cache=True)
def calculate_distane2d(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
) -> float:
    """Calculate a distance between two points on earth in meters.

    https://www.movable-type.co.uk/scripts/latlong.html
    """
    r = 6378700.0  # earth radius
    a = (
        (sin(radians(lat2 - lat1) / 2) ** 2) + cos(radians(lat1)) *
        cos(radians(lat2)) * (sin(radians(lon2 - lon1) / 2) ** 2)
    )
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


def isostring2datetime(isostring: str) -> datetime:
    """Convert ISO8601 date string to datetime"""
    return datetime.strptime(isostring, '%Y-%m-%dT%H:%M:%SZ')


def convert_mps2kmph(mps: float) -> float:
    """Convert speed from meter per second to km per hour"""
    return mps * 18 / 5


def normalize(
        floats: list[float],
        k: int = 2,
        rel_tol=0.3,
) -> list[float]:
    """Check that each value is close to K closes neighbors by rel_tol"""
    size = len(floats) - 1
    for i, current_value in enumerate(floats):
        left = max((i - k, 0))
        right = min((i + k + 1, size))
        neighbors_median = median(
            floats[left:i] + floats[min((i, size - 1)):right],
        )
        if current_value != 0.0 and not isclose(
            current_value,
            neighbors_median,
            rel_tol=rel_tol,
        ):
            floats[i] = neighbors_median


@dataclass
class Tick:
    lat: float
    lon: float
    elevation: float
    time: datetime
    power: Optional[int] = None
    temperature: Optional[int] = None
    heart_rate: Optional[int] = None
    cadence: Optional[int] = None

    def _ensure_other_is_tick(self, other: Any) -> None:
        if not isinstance(other, self.__class__):
            raise TypeError(f'Can not compare {other.__class__} and Tick')

    def distance_to(self, other: Any) -> float:
        """Distance betweeen two Ticks in meters"""
        self._ensure_other_is_tick(other)
        return calculate_distane2d(self.lat, self.lon, other.lat, other.lon)

    def timedelta(self, other: Any) -> timedelta:
        self._ensure_other_is_tick(other)
        # ensure timedelta is positive
        if other.time > self.time:
            return other.time - self.time
        return self.time - other.time

    def speed_mps(self, other: Any) -> float:
        """Speed between tow Ticks in km/h"""
        self._ensure_other_is_tick(other)
        meters: float = self.distance_to(other)
        seconds: float = self.timedelta(other).total_seconds()
        return meters / seconds

    def speed_kmph(self, other: Any) -> float:
        return convert_mps2kmph(self.speed_mps(other))


class GPXActivity:
    def __init__(self, root: Element) -> None:
        self.root = root
        self.namespaces = {
            'xmlns': 'http://www.topografix.com/GPX/1/1',
            'gpxtpx': (
                'http://www.garmin.com/xmlschemas'
                '/TrackPointExtension/v1'
            ),
        }
        self._ticks: list[Tick] = []

    @classmethod
    def fromstring(cls, xml_raw: Union[str, bytes]) -> 'GPXActivity':
        return cls(root=fromstring(xml_raw))

    @classmethod
    def fromfile(cls, xml_file_path: Union[str, Path]) -> 'GPXActivity':
        return cls(root=parse(xml_file_path))

    @property
    def start_time(self) -> datetime:
        xpath = './xmlns:metadata/xmlns:time'
        return isostring2datetime(self.root.find(xpath, self.namespaces).text)

    @property
    def finish_time(self) -> datetime:
        return self.ticks()[-1].time

    @property
    def duration(self) -> timedelta:
        return self.finish_time - self.start_time

    @property
    def name(self) -> str:
        xpath = './xmlns:trk/xmlns:name'
        return self.root.find(xpath, self.namespaces).text

    def _parse_ticks(self) -> None:
        xpath = './xmlns:trk/xmlns:trkseg/xmlns:trkpt'
        for trkpt in self.root.findall(xpath, self.namespaces):
            lat = float(trkpt.attrib['lat'])
            lon = float(trkpt.attrib['lon'])
            ele = float(trkpt.find('xmlns:ele', self.namespaces).text)
            time = isostring2datetime(
                trkpt.find('xmlns:time', self.namespaces).text,
            )
            # optonal
            try:
                power = int(trkpt.find(
                    'xmlns:extensions/xmlns:power',
                    self.namespaces,
                ).text)
            except AttributeError:
                power = None
            try:
                atemp = int(trkpt.find(
                    'xmlns:extensions/gpxtpx:TrackPointExtension/gpxtpx:atemp',
                    self.namespaces,
                ).text)
            except AttributeError:
                atemp = None
            try:
                hr = int(trkpt.find(
                    'xmlns:extensions/gpxtpx:TrackPointExtension/gpxtpx:hr',
                    self.namespaces,
                ).text)
            except AttributeError:
                hr = None
            try:
                cad = int(trkpt.find(
                    'xmlns:extensions/gpxtpx:TrackPointExtension/gpxtpx:cad',
                    self.namespaces,
                ).text)
            except AttributeError:
                cad = None
            tick = Tick(lat, lon, ele, time, power, atemp, hr, cad)
            self._ticks.append(tick)

    def ticks(self) -> list[Tick]:
        if not self._ticks:
            self._parse_ticks()
        return self._ticks

    @property
    def elevation(self) -> list[Optional[float]]:
        return [tick.elevation for tick in self.ticks()]

    @property
    def heart_rate(self) -> list[Optional[int]]:
        return [tick.heart_rate for tick in self.ticks()]

    @property
    def heart_rate_max(self) -> int:
        return max([hr for hr in self.heart_rate if hr])

    @property
    def heart_rate_avg(self) -> int:
        return mean([hr for hr in self.heart_rate if hr])

    @property
    def power(self) -> list[Optional[int]]:
        return [tick.power for tick in self.ticks()]

    @property
    def power_max(self) -> int:
        return max([power for power in self.power if power])

    @property
    def power_avg(self) -> int:
        # do not include zeros
        return mean([power for power in self.power if power])

    @property
    def power_median(self) -> int:
        # do not include zeros
        return median([power for power in self.power if power])

    @property
    def cadence(self) -> list[Optional[int]]:
        return [tick.cadence for tick in self.ticks()]

    @property
    def cadence_max(self) -> int:
        return max([cadence for cadence in self.cadence if cadence])

    @property
    def cadence_avg(self) -> int:
        return mean([cadence for cadence in self.cadence if cadence])

    @property
    def cadence_median(self) -> int:
        return median([cadence for cadence in self.cadence if cadence])

    @property
    def temperature(self) -> list[Optional[int]]:
        return [tick.temperature for tick in self.ticks()]

    @property
    def temperature_avg(self) -> int:
        return mean([temp for temp in self.temperature if temp])

    @property
    def coordinates2d(self) -> list[tuple[float, float]]:
        return [(tick.lat, tick.lon) for tick in self.ticks()]

    @property
    def coordinates3d(self) -> list[tuple[float, float, float]]:
        return [(tick.lat, tick.lon, tick.elevation) for tick in self.ticks()]

    @property
    def distance(self) -> int:
        """Activity total distance in meters"""
        meters = 0.0
        ticks = self.ticks()
        for previous, current in zip(ticks, ticks[1:]):
            meters += current.distance_to(previous)
        return meters

    @property
    def speed(self) -> list[float]:
        """Activity speed for each tick in kmph"""
        speeds: list[float] = []
        ticks = self.ticks()
        for previous, current in zip(ticks, ticks[1:]):
            speeds.append(current.speed_kmph(previous))
        normalize(speeds, k=5, rel_tol=0.1)
        return speeds

    @property
    def speed_avg(self) -> float:
        return mean(self.speed)

    @property
    def speed_median(self) -> float:
        return median(self.speed)

    @property
    def speed_max(self) -> float:
        return max(self.speed)
