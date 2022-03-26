from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from math import radians
from math import sin
from math import cos
from math import atan2
from typing import Optional
from typing import Any
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
    time: str
    power: Optional[int] = None
    temperature: Optional[int] = None
    heart_rate: Optional[int] = None
    cadence: Optional[int] = None

    def distance_to(self, other: Any) -> float:
        '''distance betweeen two Ticks in meters'''
        if not isinstance(other, self.__class__):
            raise TypeError(f'Can not compare {other.__class__} and Tick')
        return calculate_distane2d(self.lat, self.lon, other.lat, other.lon)


def str2dt(isostring: str) -> datetime:
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
    def start_time(self) -> str:
        xpath = './xmlns:metadata/xmlns:time'
        return self.root.find(xpath, self.namespaces).text

    @property
    def finish_time(self) -> str:
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
            time = trkpt.find('xmlns:time', self.namespaces).text
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
    def power(self) -> list[Optional[int]]:
        return [tick.power for tick in self.ticks()]

    @property
    def cadence(self) -> list[Optional[int]]:
        return [tick.cadence for tick in self.ticks()]

    @property
    def temperature(self) -> list[Optional[int]]:
        return [tick.temperature for tick in self.ticks()]

    @property
    def coordinates2d(self) -> list[tuple[float, float]]:
        return [(tick.lat, tick.lon) for tick in self.ticks()]

    @property
    def distance(self) -> float:
        """Activity total distance in meters"""
        meters = 0.0
        ticks = self.ticks()
        for previous, current in zip(ticks, ticks[1:]):
            meters += current.distance_to(previous)
        return meters
