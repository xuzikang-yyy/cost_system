/* 核价系统通用交互与图表主题 */
(function () {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const toggle = document.getElementById('sidebarToggle');

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('show');
    if (toggle) {
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', '打开导航');
    }
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      const open = sidebar.classList.toggle('open');
      overlay.classList.toggle('show', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? '关闭导航' : '打开导航');
    });
  }
  if (overlay) overlay.addEventListener('click', closeSidebar);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeSidebar();
  });
  window.addEventListener('resize', function () {
    if (window.innerWidth > 992) closeSidebar();
  });

  const palette = ['#17617c', '#c1842f', '#4f8f7b', '#8a6fa8', '#b85450', '#5f7d95', '#d3a45c'];
  const axisColor = '#8b98a3';
  const lineColor = '#e6ebef';

  const baseTooltip = {
    backgroundColor: 'rgba(255,255,255,.98)',
    borderColor: '#dfe6eb',
    borderWidth: 1,
    padding: [10, 12],
    textStyle: { color: '#28323c', fontSize: 12 },
    extraCssText: 'box-shadow:0 8px 24px rgba(16,36,46,.10);border-radius:8px;'
  };

  function baseAxis(extra) {
    return Object.assign({
      axisLine: { lineStyle: { color: lineColor } },
      axisTick: { show: false },
      axisLabel: { color: axisColor, fontSize: 11 },
      splitLine: { lineStyle: { color: lineColor, type: 'dashed' } }
    }, extra || {});
  }

  function makeChart(id, option) {
    const el = document.getElementById(id);
    if (!el || typeof echarts === 'undefined') return null;
    const chart = echarts.init(el, null, { renderer: 'canvas' });
    chart.setOption(Object.assign({
      color: palette,
      textStyle: { fontFamily: '"PingFang SC","Microsoft YaHei",sans-serif' },
      tooltip: baseTooltip
    }, option));
    const observer = new ResizeObserver(function () { chart.resize(); });
    observer.observe(el);
    window.addEventListener('resize', function () { chart.resize(); });
    return chart;
  }

  function lineOption(config) {
    const series = (config.series || []).map(function (item, index) {
      return {
        name: item.name,
        type: 'line',
        smooth: 0.35,
        symbol: 'circle',
        symbolSize: 5,
        showSymbol: config.showSymbol !== false,
        data: item.data,
        lineStyle: { width: 2, color: palette[index % palette.length] },
        itemStyle: { color: palette[index % palette.length] },
        areaStyle: config.area === false ? null : {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: palette[index % palette.length] + '2b' },
            { offset: 1, color: palette[index % palette.length] + '00' }
          ])
        }
      };
    });
    return {
      grid: { left: 8, right: 28, top: 30, bottom: 4, containLabel: true },
      legend: config.legend === false ? { show: false } : {
        top: 0, right: 0, icon: 'roundRect', itemWidth: 9, itemHeight: 9,
        textStyle: { color: '#6c7a86', fontSize: 11 }
      },
      tooltip: Object.assign({ trigger: 'axis' }, baseTooltip),
      xAxis: baseAxis({ type: 'category', boundaryGap: false, data: config.labels, splitLine: { show: false } }),
      yAxis: baseAxis({
        type: 'value',
        axisLine: { show: false },
        name: config.yName || '',
        nameTextStyle: { color: axisColor, fontSize: 10, padding: [0, 0, 0, -6] },
        scale: config.scale !== false
      }),
      series: series
    };
  }

  function barOption(config) {
    const horizontal = config.horizontal;
    const categoryAxis = baseAxis({
      type: 'category',
      data: config.labels,
      splitLine: { show: false },
      axisLabel: { color: config.coloredLabels ? undefined : axisColor, fontSize: 11, color: '#5d6b76', interval: 0,
        formatter: config.labelFormatter || undefined }
    });
    const valueAxis = baseAxis({ type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: lineColor, type: 'dashed' } } });
    return {
      grid: { left: 8, right: 18, top: 24, bottom: 4, containLabel: true },
      tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' } }, baseTooltip),
      xAxis: horizontal ? valueAxis : categoryAxis,
      yAxis: horizontal ? categoryAxis : valueAxis,
      series: [{
        type: 'bar',
        data: (config.values || []).map(function (value, index) {
          return {
            value: value,
            itemStyle: {
              borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
              color: config.colors ? config.colors[index] : palette[index % palette.length]
            }
          };
        }),
        barMaxWidth: config.barMaxWidth || 26,
        label: config.showLabel ? {
          show: true, position: horizontal ? 'right' : 'top',
          fontSize: 10, color: '#6c7a86',
          formatter: config.labelFormat || '{c}'
        } : { show: false },
        markLine: config.reference ? {
          symbol: 'none',
          silent: true,
          lineStyle: { color: '#b8433c', type: 'dashed', width: 1.2 },
          label: { formatter: '参考 ' + config.reference, fontSize: 10, color: '#b8433c', position: 'insideEndTop' },
          data: [{ yAxis: config.reference }]
        } : undefined
      }]
    };
  }

  function pieOption(config) {
    return {
      tooltip: Object.assign({ trigger: 'item' }, baseTooltip),
      legend: {
        orient: 'vertical', right: 0, top: 'center', icon: 'circle',
        itemWidth: 8, itemHeight: 8,
        textStyle: { color: '#5d6b76', fontSize: 11.5 },
        formatter: function (name) { return name; }
      },
      series: [{
        type: 'pie',
        radius: config.radius || ['52%', '74%'],
        center: ['36%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 13, fontWeight: 600, color: '#17222b', formatter: '{b}\n{d}%' }
        },
        labelLine: { show: false },
        data: (config.labels || []).map(function (label, index) {
          return {
            name: label,
            value: (config.values || [])[index],
            itemStyle: { color: palette[index % palette.length] }
          };
        })
      }]
    };
  }

  window.CostUI = {
    palette: palette,
    makeChart: makeChart,
    lineOption: lineOption,
    barOption: barOption,
    pieOption: pieOption,
    baseTooltip: baseTooltip,
    axisColor: axisColor
  };
})();
