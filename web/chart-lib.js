/*
 * JCIC Charts - 極簡、零依賴的 SVG 折線圖 / 長條圖元件
 * 遵循 dataviz skill 的規格：2px 線寬、4px 圓角長條端點、baseline 方角、
 * hairline 格線、hover crosshair + tooltip、legend（>=2 條線才顯示）。
 * 沒有用任何外部圖表函式庫，純手刻 SVG，離線也能開。
 */
(function (global) {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function el(tag, attrs) {
    var e = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    }
    return e;
  }

  function fmtNum(v, maxFrac) {
    if (typeof v !== 'number' || isNaN(v)) return '';
    return v.toLocaleString('zh-Hant-TW', { maximumFractionDigits: maxFrac === undefined ? 2 : maxFrac });
  }

  // "nice" tick step so axis labels land on round numbers
  function niceTicks(min, max, count) {
    if (min === max) { min -= 1; max += 1; }
    var range = max - min;
    var rawStep = range / count;
    var mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
    var norm = rawStep / mag;
    var step;
    if (norm < 1.5) step = 1 * mag;
    else if (norm < 3) step = 2 * mag;
    else if (norm < 7) step = 5 * mag;
    else step = 10 * mag;
    var niceMin = Math.floor(min / step) * step;
    var niceMax = Math.ceil(max / step) * step;
    var ticks = [];
    for (var t = niceMin; t <= niceMax + step * 0.001; t += step) ticks.push(Math.round(t * 1e6) / 1e6);
    return { ticks: ticks, min: niceMin, max: niceMax };
  }

  function makeTooltip(hostEl) {
    var tip = document.createElement('div');
    tip.className = 'jc-tooltip';
    tip.style.display = 'none';
    hostEl.appendChild(tip);
    return tip;
  }

  function positionTooltip(tip, hostEl, x, y) {
    var hostRect = hostEl.getBoundingClientRect();
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    var left = x + 14, top = y - th - 10;
    if (left + tw > hostRect.width) left = x - tw - 14;
    if (top < 0) top = y + 14;
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }

  // ---------------- Line chart ----------------
  function renderLineChart(container, cfg) {
    container.innerHTML = '';
    var series = cfg.series || [];
    var labels = cfg.labels || [];
    var unit = cfg.unit || '';
    var showLegend = series.length >= 2;

    var wrap = document.createElement('div');
    wrap.className = 'jc-chart-wrap';
    container.appendChild(wrap);

    if (showLegend) {
      var legend = document.createElement('div');
      legend.className = 'jc-legend';
      series.forEach(function (s) {
        var item = document.createElement('span');
        item.className = 'jc-legend-item';
        var swatch = document.createElement('span');
        swatch.className = 'jc-legend-swatch';
        swatch.style.background = s.color;
        item.appendChild(swatch);
        var txt = document.createElement('span');
        txt.textContent = s.label;
        item.appendChild(txt);
        legend.appendChild(item);
      });
      wrap.appendChild(legend);
    }

    var svgHost = document.createElement('div');
    svgHost.className = 'jc-svg-host';
    wrap.appendChild(svgHost);

    if (!labels.length || !series.length) {
      var empty = document.createElement('div');
      empty.className = 'jc-empty';
      empty.textContent = '沒有可顯示的資料';
      svgHost.appendChild(empty);
      return;
    }

    var W = 960, H = 340;
    var padL = 60, padR = 16, padT = 16, padB = 34;
    var plotW = W - padL - padR, plotH = H - padT - padB;

    var allVals = [];
    series.forEach(function (s) { s.data.forEach(function (v) { if (typeof v === 'number') allVals.push(v); }); });
    var dataMin = Math.min.apply(null, allVals);
    var dataMax = Math.max.apply(null, allVals);
    var margin = (dataMax - dataMin) * 0.1 || Math.abs(dataMax || 1) * 0.1;
    var ny = niceTicks(dataMin - margin, dataMax + margin, 5);

    var n = labels.length;
    function xAt(i) { return n <= 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW; }
    function yAt(v) { return padT + plotH - ((v - ny.min) / (ny.max - ny.min)) * plotH; }

    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'jc-svg' });

    // gridlines + y ticks
    var gridColor = cssVar('--gridline');
    var mutedColor = cssVar('--text-muted');
    var baselineColor = cssVar('--baseline');

    ny.ticks.forEach(function (t) {
      var y = yAt(t);
      svg.appendChild(el('line', { x1: padL, x2: W - padR, y1: y, y2: y, stroke: gridColor, 'stroke-width': 1 }));
      var label = el('text', { x: padL - 8, y: y + 3, 'text-anchor': 'end', class: 'jc-axis-label' });
      label.textContent = fmtNum(t, 0);
      svg.appendChild(label);
    });
    svg.appendChild(el('line', { x1: padL, x2: padL, y1: padT, y2: padT + plotH, stroke: baselineColor, 'stroke-width': 1 }));

    // x labels (sparse) - always include the last point, but skip the
    // second-to-last regular tick if it would sit too close and collide
    var maxXLabels = 9;
    var xStep = Math.max(1, Math.ceil(n / maxXLabels));
    var lastShownIdx = -Infinity;
    for (var i = 0; i < n; i += xStep) {
      if (n - 1 - i < xStep && i !== n - 1) continue; // would collide with forced last label
      var xl = el('text', { x: xAt(i), y: H - padB + 18, 'text-anchor': i === 0 ? 'start' : 'middle', class: 'jc-axis-label' });
      xl.textContent = labels[i];
      svg.appendChild(xl);
      lastShownIdx = i;
    }
    if (lastShownIdx !== n - 1) {
      var xlLast = el('text', { x: xAt(n - 1), y: H - padB + 18, 'text-anchor': 'end', class: 'jc-axis-label' });
      xlLast.textContent = labels[n - 1];
      svg.appendChild(xlLast);
    }

    // series lines
    series.forEach(function (s) {
      var d = '';
      var started = false;
      s.data.forEach(function (v, i) {
        if (v === null || v === undefined || isNaN(v)) { started = false; return; }
        var x = xAt(i), y = yAt(v);
        d += (started ? ' L ' : ' M ') + x + ',' + y;
        started = true;
      });
      svg.appendChild(el('path', { d: d.trim(), fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    });

    // hover crosshair group
    var crosshair = el('line', { class: 'jc-crosshair', y1: padT, y2: padT + plotH, style: 'display:none' });
    svg.appendChild(crosshair);
    var hoverDots = series.map(function (s) {
      var c = el('circle', { r: 4.5, fill: s.color, stroke: cssVar('--surface-1'), 'stroke-width': 2, style: 'display:none' });
      svg.appendChild(c);
      return c;
    });

    var captureRect = el('rect', { x: padL, y: padT, width: plotW, height: plotH, fill: 'transparent', style: 'cursor:crosshair' });
    svg.appendChild(captureRect);

    svgHost.appendChild(svg);
    var tip = makeTooltip(wrap);

    function onMove(evt) {
      var rect = svg.getBoundingClientRect();
      var scaleX = W / rect.width;
      var px = (evt.clientX - rect.left) * scaleX;
      var idx = Math.round(((px - padL) / plotW) * (n - 1));
      idx = Math.max(0, Math.min(n - 1, idx));
      var x = xAt(idx);
      crosshair.setAttribute('x1', x); crosshair.setAttribute('x2', x);
      crosshair.style.display = '';

      var rows = [];
      series.forEach(function (s, si) {
        var v = s.data[idx];
        var dot = hoverDots[si];
        if (v === null || v === undefined || isNaN(v)) { dot.style.display = 'none'; return; }
        dot.setAttribute('cx', x); dot.setAttribute('cy', yAt(v)); dot.style.display = '';
        rows.push({ label: s.label, color: s.color, value: v });
      });

      tip.innerHTML = '';
      var titleDiv = document.createElement('div');
      titleDiv.className = 'jc-tooltip-title';
      titleDiv.textContent = labels[idx];
      tip.appendChild(titleDiv);
      rows.forEach(function (r) {
        var row = document.createElement('div');
        row.className = 'jc-tooltip-row';
        var key = document.createElement('span');
        key.className = 'jc-tooltip-key';
        key.style.background = r.color;
        row.appendChild(key);
        var name = document.createElement('span');
        name.className = 'jc-tooltip-name';
        name.textContent = r.label;
        row.appendChild(name);
        var val = document.createElement('span');
        val.className = 'jc-tooltip-val';
        val.textContent = fmtNum(r.value) + (unit ? (' ' + unit) : '');
        row.appendChild(val);
        tip.appendChild(row);
      });
      tip.style.display = 'block';
      var hostRect = wrap.getBoundingClientRect();
      positionTooltip(tip, wrap, (evt.clientX - hostRect.left), (evt.clientY - hostRect.top));
    }
    function onLeave() {
      crosshair.style.display = 'none';
      hoverDots.forEach(function (d) { d.style.display = 'none'; });
      tip.style.display = 'none';
    }
    captureRect.addEventListener('mousemove', onMove);
    captureRect.addEventListener('mouseleave', onLeave);
  }

  // ---------------- Bar chart (horizontal) ----------------
  function renderBarChart(container, cfg) {
    container.innerHTML = '';
    var categories = cfg.categories || [];
    var values = cfg.values || [];
    var colors = cfg.colors || [];
    var unit = cfg.unit || '';

    var wrap = document.createElement('div');
    wrap.className = 'jc-chart-wrap';
    container.appendChild(wrap);

    if (!categories.length) {
      var empty = document.createElement('div');
      empty.className = 'jc-empty';
      empty.textContent = '沒有可顯示的資料';
      wrap.appendChild(empty);
      return;
    }

    var rowH = 28, barH = 18;
    var W = 960;
    var padL = 140, padR = 60, padT = 8, padB = 8;
    var plotW = W - padL - padR;
    var plotH = categories.length * rowH;
    var H = plotH + padT + padB;

    var maxVal = Math.max.apply(null, values.map(function (v) { return v || 0; }).concat([0]));
    var ny = niceTicks(0, maxVal * 1.08 || 1, 4);

    function xAt(v) { return padL + ((v - ny.min) / (ny.max - ny.min)) * plotW; }

    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'jc-svg jc-svg-bar' });
    var gridColor = cssVar('--gridline');
    var baselineColor = cssVar('--baseline');

    ny.ticks.forEach(function (t) {
      var x = xAt(t);
      svg.appendChild(el('line', { x1: x, x2: x, y1: padT, y2: padT + plotH, stroke: gridColor, 'stroke-width': 1 }));
      var label = el('text', { x: x, y: padT + plotH + 16, 'text-anchor': 'middle', class: 'jc-axis-label' });
      label.textContent = fmtNum(t, 0);
      svg.appendChild(label);
    });
    svg.appendChild(el('line', { x1: padL, x2: padL, y1: padT, y2: padT + plotH, stroke: baselineColor, 'stroke-width': 1 }));

    var tip = makeTooltip(wrap);

    categories.forEach(function (cat, i) {
      var y = padT + i * rowH + (rowH - barH) / 2;
      var val = values[i] || 0;
      var xEnd = xAt(val);
      var barW = Math.max(0, xEnd - padL);
      var color = colors[i] || cssVar('--series-1');

      var catLabel = el('text', { x: padL - 8, y: y + barH / 2 + 4, 'text-anchor': 'end', class: 'jc-axis-label jc-cat-label' });
      catLabel.textContent = cat;
      var titleTag = document.createElementNS(SVG_NS, 'title');
      titleTag.textContent = cat;
      catLabel.appendChild(titleTag);
      svg.appendChild(catLabel);

      var rectGroup = el('g', { class: 'jc-bar-group' });
      var hitRect = el('rect', { x: padL, y: y - 3, width: plotW, height: barH + 6, fill: 'transparent' });
      var bar = el('rect', {
        x: padL, y: y, width: Math.max(barW, 2), height: barH,
        rx: 4, ry: 4, fill: color
      });
      rectGroup.appendChild(bar);
      rectGroup.appendChild(hitRect);
      svg.appendChild(rectGroup);

      (function (cat, val, color, y) {
        rectGroup.addEventListener('mousemove', function (evt) {
          bar.setAttribute('opacity', '0.85');
          tip.innerHTML = '';
          var row = document.createElement('div');
          row.className = 'jc-tooltip-row';
          var key = document.createElement('span');
          key.className = 'jc-tooltip-key';
          key.style.background = color;
          row.appendChild(key);
          var name = document.createElement('span');
          name.className = 'jc-tooltip-name';
          name.textContent = cat;
          row.appendChild(name);
          var v = document.createElement('span');
          v.className = 'jc-tooltip-val';
          v.textContent = fmtNum(val) + (unit ? (' ' + unit) : '');
          row.appendChild(v);
          tip.appendChild(row);
          tip.style.display = 'block';
          var hostRect = wrap.getBoundingClientRect();
          positionTooltip(tip, wrap, (evt.clientX - hostRect.left), (evt.clientY - hostRect.top));
        });
        rectGroup.addEventListener('mouseleave', function () {
          bar.setAttribute('opacity', '1');
          tip.style.display = 'none';
        });
      })(cat, val, color, y);
    });

    var svgHost = document.createElement('div');
    svgHost.className = 'jc-svg-host';
    svgHost.style.setProperty('--jc-bar-aspect', (H / W));
    svgHost.appendChild(svg);
    wrap.appendChild(svgHost);
  }

  global.JcicCharts = { renderLineChart: renderLineChart, renderBarChart: renderBarChart };
})(window);
