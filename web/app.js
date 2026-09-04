(function () {
  'use strict';

  var CATALOG = window.JCIC_CATALOG || [];
  var CATEGORY_ORDER = window.JCIC_CATEGORY_ORDER || [];

  var sidebarEl = document.getElementById('category-list');
  var mainEl = document.getElementById('main');

  var loadedCategories = {};

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  var SERIES_COLORS = ['--series-1', '--series-2', '--series-3', '--series-4', '--series-5', '--series-6', '--series-7', '--series-8'];

  function seriesColor(i) {
    return cssVar(SERIES_COLORS[i % SERIES_COLORS.length]);
  }

  // 側邊選單每個資料集項目前面的小圖示，用來提示「這是可以點開看圖表的項目」，
  // 取代原本編號（1-1、6-1 這種）在側邊選單裡的視覺角色。長條圖造型呼應「點開會
  // 看到圖表」這件事，用 currentColor 讓顏色完全交給 CSS（預設/hover/active 三種
  // 狀態）控制。
  var DATASET_ICON_SVG = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<rect x="1.5" y="9" width="3" height="5.5" rx="0.75" fill="currentColor"/>' +
    '<rect x="6.5" y="5.5" width="3" height="9" rx="0.75" fill="currentColor"/>' +
    '<rect x="11.5" y="1.5" width="3" height="13" rx="0.75" fill="currentColor"/>' +
    '</svg>';

  // 顯示名稱簡化：拿掉「統計趨勢資料」這種贅字、把「新增」用引號括起來提醒是
  // 不同於存量的另一筆資料、拿掉「（中央銀行金融統計月報）」括號附註；6-3 這筆
  // 的名稱不適合用規則簡化，直接用對照表換成比較好懂的說法。catalog/bundle 資料
  // 本身的 key（item.file）完全不受影響，只影響畫面上顯示的文字。
  function simplifyLabel(text) {
    var OVERRIDES = {
      '未到期分期償還預借現金餘額統計表': '未到期的預借現金餘額統計',
      '信用卡循環信用金額統計表': '信用卡循環信用金額統計'
    };
    if (OVERRIDES[text]) return OVERRIDES[text];
    var out = text;
    out = out.replace(/（中央銀行金融統計月報）/g, '');
    out = out.replace(/統計趨勢資料/g, '');
    out = out.replace('新增', '「新增」');
    return out;
  }

  // 側邊選單的顯示名稱拿掉開頭的「1-1 」「6-1 」這種 JCIC 編號前綴，讓清單看起來
  // 更乾淨，並套用上面的簡化規則；資料集詳情頁的標題、以及所有 catalog/bundle
  // 資料本身的 key 都不受影響，編號還是完整保留在別的地方，只是側邊選單不顯示。
  function sidebarLabel(filename) {
    return simplifyLabel(filename.replace(/\.csv$/i, '').replace(/^\d+-\d+\s+/, ''));
  }

  // 資料集詳情頁標題：保留開頭的 JCIC 編號（方便對照官方資料），其餘文字套用跟
  // 側邊選單一樣的簡化規則。
  function detailTitle(filename) {
    // 資料集詳情頁標題現在跟側邊選單一樣，不顯示 JCIC 編號前綴（2026-09-04
    // 使用者確認連詳情頁也不要留編號），直接沿用 sidebarLabel() 的邏輯。
    return sidebarLabel(filename);
  }

  // ---------- Build sidebar ----------
  function buildSidebar() {
    var byCategory = {};
    CATALOG.forEach(function (item) {
      (byCategory[item.category] = byCategory[item.category] || []).push(item);
    });
    var order = CATEGORY_ORDER.length ? CATEGORY_ORDER : Object.keys(byCategory);

    sidebarEl.innerHTML = '';
    order.forEach(function (cat, idx) {
      var items = byCategory[cat];
      if (!items) return;
      var catDiv = document.createElement('div');
      catDiv.className = 'category' + (idx === 0 ? ' open' : '');

      var header = document.createElement('div');
      header.className = 'category-header';
      var nameSpan = document.createElement('span');
      nameSpan.textContent = cat;
      var countSpan = document.createElement('span');
      countSpan.className = 'count';
      countSpan.textContent = items.length + ' 個 ';
      var chevron = document.createElement('span');
      chevron.className = 'chevron';
      chevron.textContent = '▸';
      var right = document.createElement('span');
      right.style.display = 'flex';
      right.style.alignItems = 'center';
      right.appendChild(countSpan);
      right.appendChild(chevron);
      header.appendChild(nameSpan);
      header.appendChild(right);
      header.addEventListener('click', function () { catDiv.classList.toggle('open'); });
      catDiv.appendChild(header);

      var list = document.createElement('div');
      list.className = 'dataset-list';
      items.forEach(function (item) {
        var btn = document.createElement('button');
        btn.className = 'dataset-item';
        var icon = document.createElement('span');
        icon.className = 'dataset-item-icon';
        icon.innerHTML = DATASET_ICON_SVG;
        var label = document.createElement('span');
        label.className = 'dataset-item-label';
        label.textContent = sidebarLabel(item.file);
        btn.appendChild(icon);
        btn.appendChild(label);
        btn.addEventListener('click', function () { selectDataset(item, btn); });
        list.appendChild(btn);
      });
      catDiv.appendChild(list);
      sidebarEl.appendChild(catDiv);
    });
  }

  // ---------- Dataset selection ----------
  function stemOf(filename) { return filename.replace(/\.csv$/i, ''); }

  function ensureCategoryLoaded(slug) {
    if (loadedCategories[slug]) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = 'data/' + slug + '.js';
      s.onload = function () { loadedCategories[slug] = true; resolve(); };
      s.onerror = reject;
      document.body.appendChild(s);
    });
  }

  var activeBtn = null;
  function selectDataset(item, btnEl) {
    if (activeBtn) activeBtn.classList.remove('active');
    btnEl.classList.add('active');
    activeBtn = btnEl;

    mainEl.innerHTML = '<div class="loading">載入中…</div>';
    ensureCategoryLoaded(item.slug).then(function () {
      var records = ((window.JCIC_DATASETS || {})[item.slug] || {})[stemOf(item.file)] || [];
      renderDatasetView(item, records);
    }).catch(function () {
      mainEl.innerHTML = '<div class="loading">載入失敗，請重新整理頁面再試一次。</div>';
    });
  }

  // ---------- Rendering ----------
  function uniqueSorted(arr) {
    var seen = {};
    var out = [];
    arr.forEach(function (v) { if (v !== undefined && v !== null && !seen[v]) { seen[v] = true; out.push(v); } });
    out.sort();
    return out;
  }

  // 「檢視角度」這種切換整組類別的篩選器，希望固定用「總覽 → 年齡層 → 性別」
  // （其他值排在後面）的順序顯示分頁籤，而不是預設的字串排序。
  var VIEW_ANGLE_ORDER = ['總覽', '年齡層', '性別'];
  function orderDimValues(dimName, vals) {
    if (dimName !== '檢視角度') return vals;
    var out = vals.slice();
    out.sort(function (a, b) {
      var ia = VIEW_ANGLE_ORDER.indexOf(a);
      var ib = VIEW_ANGLE_ORDER.indexOf(b);
      if (ia === -1 && ib === -1) return vals.indexOf(a) - vals.indexOf(b);
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
    return out;
  }

  // 「時間區間」篩選（近1年/近3年/近5年/近10年/全部）：只套用在趨勢圖（快照
  // 比較是看單一月份的橫向比較，不受時間區間影響）。以傳入的這批 records 裡
  // 實際最新的日期為基準往回推算年份，而不是用整個資料集的最新日期，這樣就算
  // 某個細分角度的資料範圍比較短也不會算錯。
  var TIME_RANGE_YEARS = { '1y': 1, '3y': 3, '5y': 5, '10y': 10 };
  function filterRecordsByTimeRange(rows, timeRange) {
    var years = TIME_RANGE_YEARS[timeRange];
    if (!years || rows.length === 0) return rows;
    var maxDate = rows.reduce(function (m, r) { return (!m || r.date > m) ? r.date : m; }, null);
    if (!maxDate) return rows;
    var parts = maxDate.split('-');
    var cutoff = (parseInt(parts[0], 10) - years) + '-' + (parts[1] || '01');
    return rows.filter(function (r) { return r.date >= cutoff; });
  }

  function renderDatasetView(item, records) {
    var dims = item.dimensions || [];
    var metricsOrderHint = (item.metrics && item.metrics.length) ? item.metrics : null;

    var state = {
      metric: null,
      timeRange: 'all',
      dimFilters: {},
      dimSelected: {}
    };

    // 有些合併資料集（例如把「總覽／年齡層／性別」併成同一筆）在不同「檢視角度」
    // 下可用的指標並不完全一樣（像房貸總覽有「平均金額」、年齡層/性別版才有
    // 「平均利率」），所以「指標」清單要依目前的 dimFilters 動態算，不能整份
    // 資料集固定用同一份 metrics 清單。
    function computeAvailableMetrics() {
      var pool = records.filter(function (r) { return dims.slice(1).every(function (d) { return r[d] === state.dimFilters[d]; }); });
      var vals = uniqueSorted(pool.map(function (r) { return r.metric; }));
      if (!metricsOrderHint) return vals;
      var ordered = metricsOrderHint.filter(function (m) { return vals.indexOf(m) !== -1; });
      vals.forEach(function (m) { if (ordered.indexOf(m) === -1) ordered.push(m); });
      return ordered;
    }

    // 先用「全部 records」（不篩指標）算出 dimFilters 的預設值，避免「要先選
    // 指標才能算 dimFilters、卻要先有 dimFilters 才能算指標」的雞生蛋問題。
    dims.slice(1).forEach(function (d) {
      var vals = orderDimValues(d, uniqueSorted(records.map(function (r) { return r[d]; })));
      var preferred = item.defaultDimFilters && item.defaultDimFilters[d];
      state.dimFilters[d] = (preferred !== undefined && vals.indexOf(preferred) !== -1) ? preferred : vals[0];
    });

    state.metric = computeAvailableMetrics()[0];

    // 再用實際選到的指標，把 dimFilters 精修一次（維持跟原本「同一指標下才有
    // 意義」的篩選邏輯一致）。
    dims.slice(1).forEach(function (d) {
      var vals = orderDimValues(d, uniqueSorted(records.filter(function (r) { return r.metric === state.metric; }).map(function (r) { return r[d]; })));
      if (vals.indexOf(state.dimFilters[d]) === -1) state.dimFilters[d] = vals[0];
    });

    if (dims.length > 0) {
      var primaryVals0 = uniqueSorted(records.filter(function (r) { return r.metric === state.metric && dimMatchesFilters(r); }).map(function (r) { return r[dims[0]]; }));
      state.dimSelected[dims[0]] = primaryVals0.slice(0, Math.min(8, primaryVals0.length));
    }

    mainEl.innerHTML = '';
    var header = document.createElement('div');
    header.className = 'ds-header';
    var h2 = document.createElement('h2');
    h2.textContent = detailTitle(item.file);
    var meta = document.createElement('div');
    meta.className = 'ds-meta';
    var metaParts = [
      item.category,
      (item.year_min && item.year_max) ? (item.year_min + ' - ' + item.year_max) : '',
      item.record_count_long + ' 筆長格式資料'
    ];
    metaParts.filter(Boolean).forEach(function (t) {
      var span = document.createElement('span');
      span.textContent = t;
      meta.appendChild(span);
    });
    header.appendChild(h2);
    header.appendChild(meta);
    mainEl.appendChild(header);

    if (item.description) {
      var descBox = document.createElement('div');
      descBox.className = 'ds-description';
      item.description.split(/\n\s*\n/).forEach(function (para) {
        if (!para.trim()) return;
        var p = document.createElement('p');
        p.textContent = para.trim();
        descBox.appendChild(p);
      });
      mainEl.appendChild(descBox);
    }

    var tabsContainer = document.createElement('div');
    tabsContainer.className = 'tabs-container';
    mainEl.appendChild(tabsContainer);

    var controlsRow = document.createElement('div');
    controlsRow.className = 'controls-row';
    mainEl.appendChild(controlsRow);

    var chartCard = document.createElement('div');
    chartCard.className = 'chart-card';
    var chartTitle = document.createElement('h3');
    chartCard.appendChild(chartTitle);
    var chartWrap = document.createElement('div');
    chartWrap.className = 'chart-wrap';
    chartCard.appendChild(chartWrap);
    var legendNote = document.createElement('div');
    legendNote.className = 'legend-note';
    chartCard.appendChild(legendNote);
    mainEl.appendChild(chartCard);

    var tableCard = document.createElement('div');
    tableCard.className = 'chart-card';
    var tableTitle = document.createElement('h3');
    tableTitle.textContent = '資料表';
    tableCard.appendChild(tableTitle);
    var tableScroll = document.createElement('div');
    tableScroll.className = 'table-scroll';
    tableCard.appendChild(tableScroll);
    mainEl.appendChild(tableCard);

    function dimMatchesFilters(r) {
      return dims.slice(1).every(function (d) { return r[d] === state.dimFilters[d]; });
    }

    function rebuildControls() {
      tabsContainer.innerHTML = '';
      controlsRow.innerHTML = '';

      var availableMetrics = computeAvailableMetrics();
      if (availableMetrics.indexOf(state.metric) === -1) state.metric = availableMetrics[0];

      if (availableMetrics.length > 1) {
        tabsContainer.appendChild(makeTabsControl('指標', availableMetrics, state.metric, function (v) {
          state.metric = v;
          rebuildControls();
          rerender();
        }));
      }

      dims.slice(1).forEach(function (d) {
        var vals = orderDimValues(d, uniqueSorted(records.filter(function (r) { return r.metric === state.metric; }).map(function (r) { return r[d]; })));
        if (vals.indexOf(state.dimFilters[d]) === -1) state.dimFilters[d] = vals[0];
        tabsContainer.appendChild(makeTabsControl(d, vals, state.dimFilters[d], function (v) {
          state.dimFilters[d] = v;
          var newAvailableMetrics = computeAvailableMetrics();
          if (newAvailableMetrics.indexOf(state.metric) === -1) state.metric = newAvailableMetrics[0];
          if (dims.length > 0) {
            var newPrimaryVals = uniqueSorted(records.filter(function (r) { return r.metric === state.metric && dimMatchesFilters(r); }).map(function (r) { return r[dims[0]]; }));
            var prevSelected = state.dimSelected[dims[0]] || [];
            var stillValid = prevSelected.filter(function (pv) { return newPrimaryVals.indexOf(pv) !== -1; });
            state.dimSelected[dims[0]] = stillValid.length > 0 ? stillValid : newPrimaryVals.slice(0, Math.min(8, newPrimaryVals.length));
          }
          rebuildControls();
          rerender();
        }));
      });

      controlsRow.appendChild(makeTimeRangeControl(state.timeRange, function (v) {
        state.timeRange = v;
        rebuildControls();
        rerender();
      }));

      if (dims.length > 0) {
        var primaryVals = uniqueSorted(records.filter(function (r) { return r.metric === state.metric && dimMatchesFilters(r); }).map(function (r) { return r[dims[0]]; }));
        if (primaryVals.length > 1) {
          controlsRow.appendChild(makeMultiSelectControl(dims[0] + '（最多8個）', primaryVals, state.dimSelected[dims[0]] || [], function (vals) {
            state.dimSelected[dims[0]] = vals.slice(0, 8);
            rerender();
          }));
        }
      }
    }

    function rerender() {
      var unit = firstUnitForMetric(records, state.metric);
      if (dims.length === 0) {
        var rowsForMetric = filterRecordsByTimeRange(records.filter(function (r) { return r.metric === state.metric; }), state.timeRange);
        renderTrendChart(chartWrap, chartTitle, legendNote, rowsForMetric, state.metric, unit, [], {});
        renderTable(tableScroll, rowsForMetric, []);
      } else {
        var selected = state.dimSelected[dims[0]] || [];
        var rangeRecords = filterRecordsByTimeRange(records.filter(function (r) { return r.metric === state.metric && dimMatchesFilters(r); }), state.timeRange);
        renderTrendChart(chartWrap, chartTitle, legendNote, rangeRecords, state.metric, unit, dims, { primary: dims[0], selected: selected, filters: state.dimFilters });
        var filtered = rangeRecords.filter(function (r) { return selected.indexOf(r[dims[0]]) !== -1; });
        renderTable(tableScroll, filtered, dims);
      }
    }

    rebuildControls();
    rerender();
  }

  function firstUnitForMetric(records, metric) {
    for (var i = 0; i < records.length; i++) {
      if (records[i].metric === metric && records[i].unit) return records[i].unit;
    }
    return '';
  }

  function makeSelectControl(labelText, options, current, onChange) {
    var wrap = document.createElement('div');
    wrap.className = 'control';
    var label = document.createElement('label');
    label.textContent = labelText;
    var select = document.createElement('select');
    options.forEach(function (opt) {
      var o = document.createElement('option');
      o.value = opt;
      o.textContent = opt;
      if (opt === current) o.selected = true;
      select.appendChild(o);
    });
    select.addEventListener('change', function () { onChange(select.value); });
    wrap.appendChild(label);
    wrap.appendChild(select);
    return wrap;
  }

  function makeTabsControl(labelText, options, current, onChange) {
    var wrap = document.createElement('div');
    wrap.className = 'tabs-group';
    var label = document.createElement('div');
    label.className = 'tabs-group-label';
    label.textContent = labelText;
    var bar = document.createElement('div');
    bar.className = 'tab-bar';
    options.forEach(function (opt) {
      var b = document.createElement('button');
      b.className = 'tab-btn' + (opt === current ? ' active' : '');
      b.type = 'button';
      b.textContent = opt;
      b.addEventListener('click', function () { if (opt !== current) onChange(opt); });
      bar.appendChild(b);
    });
    wrap.appendChild(label);
    wrap.appendChild(bar);
    return wrap;
  }

  function makeTimeRangeControl(current, onChange) {
    var wrap = document.createElement('div');
    wrap.className = 'control';
    var label = document.createElement('label');
    label.textContent = '時間區間';
    var group = document.createElement('div');
    group.className = 'btn-toggle-group';
    [['1y', '近1年'], ['3y', '近3年'], ['5y', '近5年'], ['10y', '近10年'], ['all', '全部']].forEach(function (pair) {
      var val = pair[0], txt = pair[1];
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn-toggle' + (current === val ? ' active' : '');
      b.textContent = txt;
      b.addEventListener('click', function () { if (val !== current) onChange(val); });
      group.appendChild(b);
    });
    wrap.appendChild(label);
    wrap.appendChild(group);
    return wrap;
  }

  function makeMultiSelectControl(labelText, options, current, onChange) {
    var wrap = document.createElement('div');
    wrap.className = 'control';
    var label = document.createElement('label');
    label.textContent = labelText;
    var select = document.createElement('select');
    select.multiple = true;
    select.size = Math.min(6, Math.max(3, options.length));
    options.forEach(function (opt) {
      var o = document.createElement('option');
      o.value = opt;
      o.textContent = opt;
      if (current.indexOf(opt) !== -1) o.selected = true;
      select.appendChild(o);
    });
    select.addEventListener('change', function () {
      var vals = Array.prototype.map.call(select.selectedOptions, function (o) { return o.value; });
      if (vals.length > 8) {
        vals = vals.slice(-8);
        Array.prototype.forEach.call(select.options, function (o) { o.selected = vals.indexOf(o.value) !== -1; });
      }
      onChange(vals);
    });
    wrap.appendChild(label);
    wrap.appendChild(select);
    var hint = document.createElement('div');
    hint.className = 'hint';
    hint.textContent = 'Cmd/Ctrl 點選可複選，最多 8 個';
    wrap.appendChild(hint);
    return wrap;
  }

  function renderTrendChart(chartContainer, titleEl, legendNoteEl, records, metric, unit, dims, dimCfg) {
    var labelSuffix = unit ? (' (' + unit + ')') : '';

    if (!dims || dims.length === 0) {
      var rows = records.filter(function (r) { return r.metric === metric; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
      var dates = rows.map(function (r) { return r.date; });
      titleEl.textContent = metric + labelSuffix + ' - 歷史趨勢';
      legendNoteEl.textContent = '';
      JcicCharts.renderLineChart(chartContainer, {
        labels: dates,
        unit: unit,
        series: [{ label: metric, color: seriesColor(0), data: rows.map(function (r) { return r.value; }) }]
      });
      return;
    }

    var primary = dimCfg.primary;
    var selected = (dimCfg.selected && dimCfg.selected.length) ? dimCfg.selected : [];
    var filters = dimCfg.filters || {};
    var matches = function (r) { return dims.slice(1).every(function (d) { return r[d] === filters[d]; }); };

    var allDates = uniqueSorted(records.filter(function (r) { return r.metric === metric && matches(r); }).map(function (r) { return r.date; }));

    var series = selected.map(function (val, i) {
      var rowsForVal = records.filter(function (r) { return r.metric === metric && matches(r) && r[primary] === val; });
      var byDate = {};
      rowsForVal.forEach(function (r) { byDate[r.date] = r.value; });
      return {
        label: String(val),
        color: seriesColor(i),
        data: allDates.map(function (d) { return byDate[d] !== undefined ? byDate[d] : null; })
      };
    });

    titleEl.textContent = metric + labelSuffix + (selected.length <= 1 ? ' - 歷史趨勢' : ' - 依「' + primary + '」比較趨勢');
    legendNoteEl.textContent = selected.length === 0 ? ('請在左側選擇至少一個' + primary) : '';
    JcicCharts.renderLineChart(chartContainer, { labels: allDates, unit: unit, series: series });
  }

  function renderTable(container, rows, dims) {
    container.innerHTML = '';
    var table = document.createElement('table');
    table.className = 'data-table';
    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    ['日期'].concat(dims, ['數值', '單位']).forEach(function (h) {
      var th = document.createElement('th');
      th.textContent = h;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    var sorted = rows.slice().sort(function (a, b) { return a.date < b.date ? 1 : -1; }).slice(0, 500);
    sorted.forEach(function (r) {
      var tr = document.createElement('tr');
      var dateTd = document.createElement('td');
      dateTd.textContent = r.date;
      tr.appendChild(dateTd);
      dims.forEach(function (d) {
        var td = document.createElement('td');
        td.textContent = r[d] !== undefined ? r[d] : '';
        tr.appendChild(td);
      });
      var valTd = document.createElement('td');
      valTd.className = 'num';
      valTd.textContent = typeof r.value === 'number' ? r.value.toLocaleString('zh-Hant-TW', { maximumFractionDigits: 4 }) : '';
      tr.appendChild(valTd);
      var unitTd = document.createElement('td');
      unitTd.textContent = r.unit || '';
      tr.appendChild(unitTd);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
    if (rows.length > 500) {
      var note = document.createElement('div');
      note.className = 'legend-note';
      note.style.padding = '6px 10px';
      note.textContent = '僅顯示最新 500 筆（共 ' + rows.length + ' 筆），完整資料請見 data/processed/ 底下的 JSON 檔。';
      container.appendChild(note);
    }
  }

  buildSidebar();
})();
