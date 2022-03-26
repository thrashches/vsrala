from dataclasses import dataclass
from datetime import datetime
from math import atan2
from math import cos
from math import radians
from math import sin
from math import sqrt
from statistics import mean
from statistics import median
from typing import Any
from typing import Optional
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import fromstring

from numba import jit  # type: ignore


@jit(nopython=True, cache=True)
def calculate_distane2d(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
) -> float:
    """Calculate distance  between two points on earth in meters.

    https://www.movable-type.co.uk/scripts/latlong.html
    """
    r = 6378700.0  # earth radius
    a = (
        (sin(radians(lat2 - lat1) / 2) ** 2) + cos(radians(lat1)) *
        cos(radians(lat2)) * (sin(radians(lon2 - lon1) / 2) ** 2)
    )
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


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

    def distance_to(self, other: Any) -> float:
        '''distance betweeen two Ticks in meters'''
        if not isinstance(other, self.__class__):
            raise TypeError(f'Can not compare {other.__class__} and Tick')
        return calculate_distane2d(self.lat, self.lon, other.lat, other.lon)


def isostring2datetime(isostring: str) -> datetime:
    return datetime.strptime(isostring, '%Y-%m-%dT%H:%M:%SZ')


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
    def fromstring(cls, xml_raw) -> 'GPXActivity':
        return cls(root=fromstring(xml_raw))

    @property
    def start_time(self) -> datetime:
        xpath = './xmlns:metadata/xmlns:time'
        return isostring2datetime(self.root.find(xpath, self.namespaces).text)

    @property
    def finish_time(self) -> datetime:
        return self.ticks()[-1].time

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
