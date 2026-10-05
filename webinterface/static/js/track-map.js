/**
 * Initialize Leaflet track maps from elements with data-track-map and data-points.
 * Interactive maps expose a cursor synced with activity charts via VsralaTrackMaps.
 */
(function () {
  var syncMaps = [];

  function latLngAtTime(points, t) {
    if (!points.length) return null;
    if (t == null) return null;
    if (t <= points[0].t) return [points[0].lat, points[0].lon];
    if (t >= points[points.length - 1].t) {
      var last = points[points.length - 1];
      return [last.lat, last.lon];
    }
    var lo = 0;
    var hi = points.length - 1;
    while (hi - lo > 1) {
      var mid = (lo + hi) >> 1;
      if (points[mid].t <= t) lo = mid;
      else hi = mid;
    }
    var a = points[lo];
    var b = points[hi];
    if (b.t === a.t) return [a.lat, a.lon];
    var k = (t - a.t) / (b.t - a.t);
    return [
      a.lat + (b.lat - a.lat) * k,
      a.lon + (b.lon - a.lon) * k,
    ];
  }

  function normalizePoints(raw, durationSec) {
    var points = raw.map(function (p, i) {
      return {
        lat: p[0],
        lon: p[1],
        t: (p.length > 2 && p[2] != null) ? Number(p[2]) : null,
        i: i,
      };
    });
    var missing = points.some(function (p) { return p.t == null || isNaN(p.t); });
    if (missing) {
      var span = durationSec > 0 ? durationSec : Math.max(points.length - 1, 1);
      points.forEach(function (p, i) {
        if (p.t == null || isNaN(p.t)) {
          p.t = points.length > 1 ? (i / (points.length - 1)) * span : 0;
        }
      });
    }
    return points;
  }

  function initMap(el) {
    if (!window.L) return;
    var raw = el.getAttribute('data-points');
    if (!raw) return;
    var points;
    try {
      points = JSON.parse(raw);
    } catch (e) {
      return;
    }
    if (!points || !points.length) return;

    var interactive = el.getAttribute('data-interactive') !== 'false';
    var durationSec = Number(el.getAttribute('data-duration') || 0);
    var timed = normalizePoints(points, durationSec);

    var map = L.map(el, {
      zoomControl: interactive,
      dragging: interactive,
      scrollWheelZoom: interactive,
      doubleClickZoom: interactive,
      boxZoom: interactive,
      keyboard: interactive,
      attributionControl: interactive,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      // OSM blocks tiles without Referer (403 "Access blocked")
      referrerPolicy: 'strict-origin-when-cross-origin',
      attribution: interactive
        ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        : '',
    }).addTo(map);

    var latlngs = timed.map(function (p) {
      return [p.lat, p.lon];
    });
    var polyline = L.polyline(latlngs, {
      color: '#FC5200',
      weight: interactive ? 4 : 3,
      opacity: 0.95,
    }).addTo(map);

    var markerR = interactive ? 7 : 5;
    L.circleMarker(latlngs[0], {
      radius: markerR,
      color: '#fff',
      weight: 2,
      fillColor: '#22c55e',
      fillOpacity: 1,
      opacity: 1,
      interactive: false,
    }).addTo(map);

    if (latlngs.length > 1) {
      L.circleMarker(latlngs[latlngs.length - 1], {
        radius: markerR,
        color: '#fff',
        weight: 2,
        fillColor: '#1c1c1e',
        fillOpacity: 1,
        opacity: 1,
        interactive: false,
      }).addTo(map);
    }

    map.fitBounds(polyline.getBounds(), { padding: [16, 16] });

    setTimeout(function () {
      map.invalidateSize();
    }, 100);

    if (!interactive) return;

    var cursor = L.circleMarker(latlngs[0], {
      radius: 7,
      color: '#fff',
      weight: 2,
      fillColor: '#FC5200',
      fillOpacity: 1,
      opacity: 0,
    }).addTo(map);
    cursor.setStyle({ fillOpacity: 0 });

    var ctrl = {
      setTime: function (t) {
        if (t == null) {
          cursor.setStyle({ opacity: 0, fillOpacity: 0 });
          return;
        }
        var ll = latLngAtTime(timed, t);
        if (!ll) return;
        cursor.setLatLng(ll);
        cursor.setStyle({ opacity: 1, fillOpacity: 1 });
      },
    };
    syncMaps.push(ctrl);
  }

  function initAll() {
    syncMaps = [];
    document.querySelectorAll('[data-track-map]').forEach(initMap);
  }

  window.VsralaTrackMaps = {
    setTime: function (t) {
      for (var i = 0; i < syncMaps.length; i++) {
        syncMaps[i].setTime(t);
      }
    },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
