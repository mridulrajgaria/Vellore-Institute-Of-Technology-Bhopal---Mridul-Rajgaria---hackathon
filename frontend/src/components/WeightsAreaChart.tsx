import React, { useEffect, useRef, useMemo } from 'react';
import * as echarts from 'echarts';
import { PortfolioWeight } from '../types';

interface WeightsAreaChartProps {
  weightsData: PortfolioWeight[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
}

// Muted, color-blind-safe categorical palette designed for dark theme.
// Neighboring bands alternate cool and warm tones for maximum adjacent contrast.
const TICKER_COLORS: Record<string, string> = {
  AMD: '#38BDF8',   // Sky blue
  BA: '#F59E0B',    // Amber
  KO: '#34D399',    // Emerald
  COST: '#EC4899',  // Pink / Rose
  PG: '#60A5FA',    // Light Blue
  MSFT: '#FB923C',  // Warm Orange
  TSLA: '#A78BFA',  // Violet
  DIS: '#2DD4BF',   // Teal
  PYPL: '#E879F9',  // Fuchsia
  GOOGL: '#FACC15', // Gold
  AMZN: '#818CF8',  // Indigo
  AAPL: '#4ADE80',  // Mint Green
  META: '#F43F5E',  // Coral / Red
  NFLX: '#94A3B8',  // Cool Slate
};

// Universe ordered by historical average portfolio weight (NFLX lowest up to AMD highest)
// so the stacked visual layers remain stable and intuitive.
const ORDERED_TICKERS = [
  'NFLX', 'META', 'AAPL', 'AMZN', 'GOOGL',
  'PYPL', 'DIS', 'TSLA', 'MSFT', 'PG',
  'COST', 'KO', 'BA', 'AMD',
];

export const WeightsAreaChart: React.FC<WeightsAreaChartProps> = ({
  weightsData,
  selectedDate,
  onSelectDate,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  // Sorted unique trading dates
  const dates = useMemo(() => {
    return Array.from(new Set(weightsData.map((d) => d.date))).sort();
  }, [weightsData]);

  useEffect(() => {
    if (!chartRef.current || weightsData.length === 0) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, 'dark');
      chartInstance.current.on('click', (params: any) => {
        if (params.name && typeof params.name === 'string') {
          onSelectDate(params.name);
        }
      });
    }

    const chart = chartInstance.current;

    // Available tickers
    const rawTickers = Array.from(new Set(weightsData.map((d) => d.ticker)));
    // Sort according to ordered stack ranking
    const tickers = ORDERED_TICKERS.filter((tk) => rawTickers.includes(tk));

    // Lookup: date -> ticker -> weight%
    const lookup: Record<string, Record<string, number>> = {};
    weightsData.forEach((w) => {
      if (!lookup[w.date]) lookup[w.date] = {};
      lookup[w.date][w.ticker] = w.weight * 100;
    });

    const seriesDataByTicker: Record<string, number[]> = {};
    tickers.forEach((tk) => {
      seriesDataByTicker[tk] = [];
    });

    dates.forEach((d) => {
      tickers.forEach((tk) => {
        seriesDataByTicker[tk].push(lookup[d]?.[tk] ?? (100 / 14));
      });
    });

    const series = tickers.map((tk) => ({
      name: tk,
      type: 'line',
      stack: 'Total',
      smooth: true,
      lineStyle: {
        width: 0.8,
        color: TICKER_COLORS[tk] || '#94A3B8',
      },
      showSymbol: false,
      areaStyle: {
        opacity: 0.75,
        color: TICKER_COLORS[tk] || '#94A3B8',
      },
      emphasis: {
        focus: 'series',
      },
      data: seriesDataByTicker[tk],
    }));

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      title: {
        text: '14-Asset Allocation Evolution (Stacked Area)',
        subtext: 'Rebalanced daily based on EMA smoothed score • Bounds [3.57%, 14.29%] • 10% daily turnover cap',
        left: '16px',
        top: '12px',
        textStyle: {
          color: '#F1F5F9',
          fontSize: 14,
          fontWeight: 600,
        },
        subtextStyle: {
          color: '#94A3B8',
          fontSize: 11,
        },
      },
      // Dedicated legend row below title with zero overlap, clickable series toggling
      legend: {
        type: 'plain',
        top: 54,
        left: '16px',
        right: '16px',
        selectedMode: true,
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 10,
        data: tickers,
        textStyle: {
          color: '#94A3B8',
          fontSize: 11,
          fontFamily: "'IBM Plex Mono', monospace",
        },
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#11161B',
        borderColor: '#252C34',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: {
          color: '#F1F5F9',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
        },
        axisPointer: {
          type: 'line',
          lineStyle: {
            color: '#38BDF8',
            width: 1.5,
            type: 'dashed',
          },
        },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return '';
          const dateStr = params[0].axisValue;
          let html = `<div style="font-family:'IBM Plex Mono', monospace; font-weight:700; font-size:12px; margin-bottom:6px; color:#38BDF8;">${dateStr}</div>`;
          html += `<div style="display:grid; grid-template-columns: repeat(2, minmax(110px, 1fr)); gap: 3px 12px; font-family:'IBM Plex Mono', monospace; font-size:11px;">`;
          params.forEach((item: any) => {
            html += `<div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="color:${item.color}; font-weight:600;">${item.seriesName}:</span>
              <span style="color:#F1F5F9; font-weight:500; margin-left:6px;">${Number(item.value).toFixed(2)}%</span>
            </div>`;
          });
          html += `</div>`;
          return html;
        },
      },
      grid: {
        left: '3%',
        right: '3%',
        bottom: '14%',
        top: 96,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates,
        axisLine: { lineStyle: { color: '#252C34' } },
        axisLabel: {
          color: '#94A3B8',
          fontSize: 10,
          fontFamily: "'IBM Plex Mono', monospace",
          formatter: (val: string) => val.slice(5), // MM-DD
        },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLine: { lineStyle: { color: '#252C34' } },
        splitLine: { lineStyle: { color: '#171D23' } },
        axisLabel: {
          color: '#94A3B8',
          fontSize: 10,
          fontFamily: "'IBM Plex Mono', monospace",
          formatter: '{value}%',
        },
      },
      dataZoom: [
        {
          type: 'slider',
          show: true,
          bottom: '1%',
          height: 18,
          borderColor: '#252C34',
          backgroundColor: '#11161B',
          fillerColor: 'rgba(56, 189, 248, 0.15)',
          handleStyle: {
            color: '#38BDF8',
          },
          textStyle: {
            color: '#94A3B8',
            fontSize: 10,
            fontFamily: "'IBM Plex Mono', monospace",
          },
        },
      ],
      series: series as any,
    };

    chart.setOption(option, true);

    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [weightsData, dates]);

  // Synchronize tooltip highlight using the exact index in the dates array (length 252)
  useEffect(() => {
    if (!chartInstance.current || !selectedDate || dates.length === 0) return;
    const dateIdx = dates.indexOf(selectedDate);
    if (dateIdx >= 0) {
      chartInstance.current.dispatchAction({
        type: 'showTip',
        seriesIndex: 0,
        dataIndex: dateIdx,
      });
    }
  }, [selectedDate, dates]);

  return (
    <div className="rounded-lg border border-border bg-surface p-4 shadow-sm">
      <div ref={chartRef} className="w-full h-[400px]" />
    </div>
  );
};
