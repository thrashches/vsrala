from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from typing import Union
from typing import Any
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import fromstring


@dataclass
class Tick:
    lat: float
    lon: float
    elevation: float
    time: str
    power: int = None
    temperature: int = None
    heart_rate: int = None
    cadence: int = None


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
        self._ticks = []

    @classmethod
    def fromstring(cls, xml_raw) -> 'GPXActivity':
        return cls(root=fromstring(xml_raw))

    def start_time(self) -> str:
        xpath = './xmlns:metadata/xmlns:time'
        return self.root.find(xpath, self.namespaces).text

    def finish_time(self) -> str:
        return self.ticks()[-1].time

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

    def elevation(self) -> list[Optional[int]]:
        return [tick.elevation for tick in self.ticks()]

    def heart_rate(self) -> list[Optional[int]]:
        return [tick.heart_rate for tick in self.ticks()]

    def power(self) -> list[Optional[int]]:
        return [tick.power for tick in self.ticks()]

    def cadence(self) -> list[Optional[int]]:
        return [tick.cadence for tick in self.ticks()]

    def temperature(self) -> list[Optional[int]]:
        return [tick.temperature for tick in self.ticks()]
