import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { NavPoint } from '../types';

interface PerformanceChartProps {
  navData: NavPoint[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
}

export const PerformanceChart: React.FC<PerformanceChartProps> = ({
  navData,
  selectedDate,
  onSelectDate,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current || navData.length === 0) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, 'dark');
      chartInstance.current.on('click', (params: any) => {
        if (params.name && typeof params.name === 'string') {
          onSelectDate(params.name);
        }
      });
    }

    const chart = chartInstance.current;
    const dates = navData.map((d) => d.date);

    // Cumulative returns in %
    const stratRet = navData.map((d) => (d.strategy_5bps - 1.0) * 100);
    const ewRet = navData.map((d) => (d.equal_weight_5bps - 1.0) * 100);
    const spyRet = navData.map((d) => (d.spy - 1.0) * 100);

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      title: {
        text: 'Cumulative Performance (Sentiment Strategy vs Equal Weight vs SPY)',
        subtext: '5 bps transaction costs applied • Reflects 2021-2022 macroeconomic tech downtrend',
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
        itemWidth: 16,
        itemHeight: 10,
        itemGap: 16,
        data: ['Sentiment Strategy (5 bps)', 'Equal Weight (5 bps)', 'S&P 500 (SPY)'],
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
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return '';
          const dateStr = params[0].axisValue;
          let html = `<div style="font-family:'IBM Plex Mono', monospace; font-weight:700; font-size:12px; margin-bottom:6px; color:#38BDF8;">${dateStr}</div>`;
          params.forEach((item: any) => {
            const val = Number(item.value);
            const colorClass = val >= 0 ? '#22C55E' : '#EF4444';
            html += `<div style="display:flex; justify-content:space-between; align-items:center; gap:16px; font-family:'IBM Plex Mono', monospace; font-size:11px; padding:2px 0;">
              <span style="color:${item.color}; font-weight:600;">${item.seriesName}:</span>
              <span style="color:${colorClass}; font-weight:500;">
                ${val >= 0 ? '+' : ''}${val.toFixed(2)}%
              </span>
            </div>`;
          });
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
          formatter: (val: string) => val.slice(5),
        },
      },
      yAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#252C34' } },
        splitLine: { lineStyle: { color: '#171D23' } },
        axisLabel: {
          color: '#94A3B8',
          fontSize: 10,
          fontFamily: "'IBM Plex Mono', monospace",
          formatter: '{value}%',
        },
      },
      series: [
        {
          name: 'Sentiment Strategy (5 bps)',
          type: 'line',
          data: stratRet,
          smooth: true,
          showSymbol: false,
          lineStyle: {
            width: 2.5,
            color: '#38BDF8', // Sky Blue Accent
          },
        },
        {
          name: 'Equal Weight (5 bps)',
          type: 'line',
          data: ewRet,
          smooth: true,
          showSymbol: false,
          lineStyle: {
            width: 1.8,
            type: 'dashed',
            color: '#94A3B8', // Slate Benchmark
          },
        },
        {
          name: 'S&P 500 (SPY)',
          type: 'line',
          data: spyRet,
          smooth: true,
          showSymbol: false,
          lineStyle: {
            width: 1.8,
            color: '#F59E0B', // Amber S&P 500
          },
        },
      ],
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
    };

    chart.setOption(option, true);

    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [navData]);

  // Synchronize vertical playhead markLine and tooltip highlight when selectedDate changes
  useEffect(() => {
    if (!chartInstance.current || !selectedDate || navData.length === 0) return;
    const dateIdx = navData.findIndex((d) => d.date === selectedDate);
    if (dateIdx >= 0) {
      chartInstance.current.setOption({
        series: [
          {
            name: 'Sentiment Strategy (5 bps)',
            markLine: {
              symbol: ['none', 'none'],
              animation: false,
              lineStyle: {
                color: '#38BDF8',
                width: 1.5,
                type: 'solid',
              },
              data: [{ xAxis: selectedDate }],
              label: { show: false },
            },
          },
        ],
      });
      chartInstance.current.dispatchAction({
        type: 'showTip',
        seriesIndex: 0,
        dataIndex: dateIdx,
      });
    }
  }, [selectedDate, navData]);

  return (
    <div className="rounded-lg border border-border bg-surface p-4 shadow-sm">
      <div ref={chartRef} className="w-full h-[400px]" />
    </div>
  );
};
