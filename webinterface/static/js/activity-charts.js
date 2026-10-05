/**
 * Render activity stream charts (speed / hr / power / elevation) with Chart.js.
 * X-axis is elapsed time; hover syncs a vertical crosshair across all charts.
 * Each chart marks its max point and draws an average horizontal line.
 * Elevation is drawn as a gray filled background on metric charts.
 */
(function () {
  var syncTime = null;
  var charts = [];
  var rafId = null;

  function pad2(n) {
    return n < 10 ? '0' + n : String(n);
  }

  function formatElapsed(sec) {
    if (sec == null || isNaN(sec)) return '';
    sec = Math.max(0, Math.round(sec));
    var h = Math.floor(sec / 3600);
    var m = Math.floor((sec % 3600) / 60);
    var s = sec % 60;
    if (h > 0) return h + ':' + pad2(m) + ':' + pad2(s);
    return m + ':' + pad2(s);
  }

  function formatValue(v) {
    if (v == null || isNaN(v)) return '';
    return Math.round(v * 10) / 10 === Math.round(v) ? String(Math.round(v)) : String(Math.round(v * 10) / 10);
  }

  function toPoints(values, times) {
    var out = [];
    var arr = values || [];
    for (var i = 0; i < arr.length; i++) {
      var y = arr[i];
      if (y === null || y === undefined) continue;
      var x = (times && times[i] != null) ? Number(times[i]) : i;
      out.push({ x: x, y: y });
    }
    return out;
  }

  function stats(points) {
    var maxPt = null;
    var sum = 0;
    for (var i = 0; i < points.length; i++) {
      var p = points[i];
      sum += p.y;
      if (!maxPt || p.y > maxPt.y) maxPt = p;
    }
    return {
      max: maxPt,
      avg: points.length ? sum / points.length : 0,
    };
  }

  function xExtent(datasets) {
    var min = Infinity;
    var max = -Infinity;
    datasets.forEach(function (pts) {
      for (var i = 0; i < pts.length; i++) {
        if (pts[i].x < min) min = pts[i].x;
        if (pts[i].x > max) max = pts[i].x;
      }
    });
    if (!isFinite(min)) min = 0;
    if (!isFinite(max) || max <= min) max = min + 1;
    return { min: min, max: max };
  }

  function yExtent(points) {
    var min = Infinity;
    var max = -Infinity;
    for (var i = 0; i < points.length; i++) {
      if (points[i].y < min) min = points[i].y;
      if (points[i].y > max) max = points[i].y;
    }
    if (!isFinite(min)) return { min: 0, max: 1 };
    if (max <= min) {
      return { min: min - 1, max: max + 1 };
    }
    var pad = (max - min) * 0.08;
    return { min: min - pad, max: max + pad };
  }

  function redrawAll() {
    rafId = null;
    for (var i = 0; i < charts.length; i++) {
      charts[i].draw();
    }
  }

  function scheduleRedraw() {
    if (rafId != null) return;
    rafId = requestAnimationFrame(redrawAll);
  }

  function setSyncTime(t) {
    if (syncTime === t) return;
    syncTime = t;
    scheduleRedraw();
    if (window.VsralaTrackMaps) {
      window.VsralaTrackMaps.setTime(t);
    }
  }

  /** Interpolate series Y at time t (data sorted by x). */
  function valueAtTime(points, t) {
    if (!points || !points.length || t == null) return null;
    if (t <= points[0].x) return points[0].y;
    if (t >= points[points.length - 1].x) return points[points.length - 1].y;

    var lo = 0;
    var hi = points.length - 1;
    while (hi - lo > 1) {
      var mid = (lo + hi) >> 1;
      if (points[mid].x <= t) lo = mid;
      else hi = mid;
    }
    var a = points[lo];
    var b = points[hi];
    if (b.x === a.x) return a.y;
    var k = (t - a.x) / (b.x - a.x);
    return a.y + (b.y - a.y) * k;
  }

  function drawValueBadge(ctx, x, y, text, color, area) {
    ctx.save();
    ctx.font = '600 11px system-ui, sans-serif';
    var padX = 6;
    var padY = 3;
    var tw = ctx.measureText(text).width;
    var bw = tw + padX * 2;
    var bh = 16;
    var bx = x + 10;
    var by = y - bh / 2;
    if (bx + bw > area.right - 2) bx = x - 10 - bw;
    if (by < area.top + 2) by = area.top + 2;
    if (by + bh > area.bottom - 2) by = area.bottom - 2 - bh;

    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(bx, by, bw, bh, 3);
    } else {
      ctx.rect(bx, by, bw, bh);
    }
    ctx.fillStyle = color;
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, bx + padX, by + bh / 2);
    ctx.restore();
  }

  var overlaysPlugin = {
    id: 'chartOverlays',
    afterDatasetsDraw: function (chart) {
      var ctx = chart.ctx;
      var area = chart.chartArea;
      var xScale = chart.scales.x;
      var yScale = chart.scales.y;
      if (!area || !xScale || !yScale) return;

      var opts = chart.options.plugins && chart.options.plugins.chartOverlays
        ? chart.options.plugins.chartOverlays
        : {};
      var avg = opts.avg;
      var color = opts.color || '#333';
      var series = opts.series || ((chart.data.datasets[0] && chart.data.datasets[0].data) || []);

      if (avg != null) {
        var avgY = yScale.getPixelForValue(avg);
        if (avgY >= area.top && avgY <= area.bottom) {
          var avgLabel = 'ср. ' + formatValue(avg);
          ctx.save();
          ctx.font = '11px system-ui, sans-serif';
          ctx.fillStyle = 'rgba(28, 28, 30, 0.55)';
          ctx.textAlign = 'right';
          ctx.textBaseline = 'bottom';
          ctx.fillText(avgLabel, area.right - 4, avgY - 2);
          ctx.restore();
        }
      }

      if (syncTime === null) return;
      var x = xScale.getPixelForValue(syncTime);
      if (x < area.left || x > area.right) return;

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(x, area.top);
      ctx.lineTo(x, area.bottom);
      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(28, 28, 30, 0.55)';
      ctx.stroke();
      ctx.restore();

      var value = valueAtTime(series, syncTime);
      if (value == null) return;
      var py = yScale.getPixelForValue(value);
      if (py < area.top || py > area.bottom) return;

      ctx.save();
      ctx.beginPath();
      ctx.arc(x, py, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#fff';
      ctx.stroke();
      ctx.restore();

      drawValueBadge(ctx, x, py, formatValue(value), color, area);
    },
  };

  function bindSyncEvents(chart) {
    var canvas = chart.canvas;

    function onMove(evt) {
      var helpers = window.Chart && window.Chart.helpers;
      if (!helpers || !helpers.getRelativePosition) return;
      var pos = helpers.getRelativePosition(evt, chart);
      var area = chart.chartArea;
      if (!area) return;
      var px = Math.min(area.right, Math.max(area.left, pos.x));
      setSyncTime(chart.scales.x.getValueForPixel(px));
    }

    function onLeave() {
      setSyncTime(null);
    }

    canvas.addEventListener('mousemove', onMove);
    canvas.addEventListener('mouseleave', onLeave);
  }

  function elevationDataset(eleData) {
    return {
      label: 'Высота',
      data: eleData,
      borderColor: 'rgba(120, 120, 128, 0.35)',
      backgroundColor: 'rgba(120, 120, 128, 0.18)',
      borderWidth: 1,
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0.15,
      fill: true,
      spanGaps: true,
      parsing: false,
      yAxisID: 'yEle',
      // Lower order draws first (behind metric series).
      order: 0,
    };
  }

  function makeChart(canvas, label, data, color, xRange, eleData) {
    if (!window.Chart || !canvas || !data.length) return null;

    var s = stats(data);
    var hasEle = eleData && eleData.length > 0;
    var eleRange = hasEle ? yExtent(eleData) : null;

    var datasets = [];
    if (hasEle) {
      datasets.push(elevationDataset(eleData));
    }

    datasets.push({
      label: label,
      data: data,
      borderColor: color,
      backgroundColor: color + '22',
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0,
      fill: !hasEle,
      spanGaps: false,
      parsing: false,
      yAxisID: 'y',
      order: 3,
    }, {
      label: 'Среднее',
      data: [
        { x: xRange.min, y: s.avg },
        { x: xRange.max, y: s.avg },
      ],
      borderColor: 'rgba(28, 28, 30, 0.4)',
      borderWidth: 1.25,
      borderDash: [6, 4],
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0,
      fill: false,
      parsing: false,
      yAxisID: 'y',
      order: 2,
    });

    if (s.max) {
      datasets.push({
        label: 'Максимум',
        data: [s.max],
        borderColor: color,
        backgroundColor: color,
        pointRadius: 5,
        pointHoverRadius: 6,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        showLine: false,
        parsing: false,
        yAxisID: 'y',
        order: 4,
      });
    }

    var scales = {
      x: {
        type: 'linear',
        min: xRange.min,
        max: xRange.max,
        bounds: 'ticks',
        grid: { color: '#f0f0f0', drawBorder: false },
        ticks: {
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 8,
          font: { size: 10 },
          color: '#8a8a8a',
          callback: function (v) {
            return formatElapsed(v);
          },
        },
      },
      y: {
        position: 'left',
        grid: { color: '#eee' },
        ticks: { font: { size: 11 } },
      },
    };

    if (hasEle) {
      scales.yEle = {
        position: 'right',
        min: eleRange.min,
        max: eleRange.max,
        display: false,
        grid: { drawOnChartArea: false },
      };
    }

    return new Chart(canvas, {
      type: 'line',
      data: { datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        normalized: true,
        parsing: false,
        interaction: {
          mode: 'nearest',
          axis: 'x',
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          chartOverlays: { avg: s.avg, color: color, series: data },
          tooltip: { enabled: false },
        },
        scales: scales,
      },
      plugins: [overlaysPlugin],
    });
  }

  function init() {
    var el = document.getElementById('activity-streams');
    if (!el || !window.Chart) return;
    var streams;
    try {
      streams = JSON.parse(el.getAttribute('data-streams') || '{}');
    } catch (e) {
      return;
    }

    var durationSec = Number(el.getAttribute('data-duration') || 0);
    var times = streams.time || null;
    if (!times || !times.length) {
      var n = Math.max(
        (streams.speed || []).length,
        (streams.hr || []).length,
        (streams.power || []).length,
        (streams.ele || []).length
      );
      var span = durationSec > 0 ? durationSec : Math.max(n - 1, 1);
      times = [];
      for (var i = 0; i < n; i++) {
        times.push(n > 1 ? (i / (n - 1)) * span : 0);
      }
    }

    var speed = toPoints(streams.speed, times);
    var hr = toPoints(streams.hr, times);
    var power = toPoints(streams.power, times);
    var ele = toPoints(streams.ele, times);
    var range = xExtent([speed, hr, power, ele]);
    if (durationSec > range.max) range.max = durationSec;

    var specs = [
      ['chart-speed', 'Скорость, км/ч', speed, '#FC5200', true],
      ['chart-hr', 'Пульс', hr, '#E8192E', true],
      ['chart-power', 'Мощность, Вт', power, '#007FB6', true],
      ['chart-ele', 'Высота, м', ele, '#6d6d78', false],
    ];

    specs.forEach(function (spec) {
      var canvas = document.getElementById(spec[0]);
      var data = spec[2];
      if (!data.length) {
        if (canvas) {
          var wrap = canvas.closest('[data-chart-panel]');
          if (wrap) wrap.classList.add('hidden');
        }
        return;
      }
      var bgEle = spec[4] ? ele : null;
      var chart = makeChart(canvas, spec[1], data, spec[3], range, bgEle);
      if (chart) {
        charts.push(chart);
        bindSyncEvents(chart);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
