import React, { useState } from 'react';
import { Table, BarChart2 } from 'lucide-react';

/**
 * Interactive SVG Bar Chart with 95% Confidence Interval Error Bars
 * Adheres to DESIGN.md Section 2 (Categorical chart palette) and Section 4
 */
export const BarChart = ({
  data = [],
  title = 'Category Breakdown with Confidence Intervals',
}) => {
  const [hoveredBar, setHoveredBar] = useState(null);
  const [viewAsTable, setViewAsTable] = useState(false);

  const width = 540;
  const height = 220;
  const padding = { top: 25, right: 20, bottom: 40, left: 45 };

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const scaleY = (val) => padding.top + plotHeight - (val / 100) * plotHeight;
  const barWidth = 64;
  const groupSpacing = plotWidth / data.length;

  return (
    <div className="w-full flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-ink-strong">{title}</span>
          <span className="text-[11px] font-mono text-ink-muted">k = {data.length} groups</span>
        </div>
        <button
          type="button"
          onClick={() => setViewAsTable(!viewAsTable)}
          className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
        >
          {viewAsTable ? (
            <>
              <BarChart2 className="w-3.5 h-3.5" /> View chart
            </>
          ) : (
            <>
              <Table className="w-3.5 h-3.5" /> View as table
            </>
          )}
        </button>
      </div>

      {viewAsTable ? (
        <div className="max-h-52 overflow-y-auto border border-hairline rounded-lg">
          <table className="w-full text-left text-xs">
            <thead className="bg-canvas text-ink-muted sticky top-0">
              <tr>
                <th className="p-2 border-b border-hairline">Category</th>
                <th className="p-2 border-b border-hairline font-mono">Value</th>
                <th className="p-2 border-b border-hairline font-mono">95% CI</th>
                <th className="p-2 border-b border-hairline font-mono">Sample (n)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {data.map((d, idx) => (
                <tr key={idx} className="hover:bg-canvas">
                  <td className="p-2 font-medium text-ink-strong">{d.label}</td>
                  <td className="p-2 font-mono font-bold text-primary">{d.value}%</td>
                  <td className="p-2 font-mono text-ink-muted">
                    [{d.ci_lower}%, {d.ci_upper}%]
                  </td>
                  <td className="p-2 font-mono text-ink-body">{d.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative w-full h-[220px] bg-canvas rounded-xl p-2 border border-hairline flex items-center justify-center select-none overflow-hidden">
          {hoveredBar && (
            <div
              className="absolute z-20 pointer-events-none bg-ink-DEFAULT text-white px-2.5 py-1.5 rounded-lg text-xs font-mono shadow-lg transition-transform"
              style={{
                left: `${hoveredBar.x - 40}px`,
                top: `${hoveredBar.y - 45}px`,
              }}
            >
              <div className="font-bold">{hoveredBar.label}: {hoveredBar.value}%</div>
              <div className="text-[10px] text-slate-300">
                CI: [{hoveredBar.ci_lower}%, {hoveredBar.ci_upper}%] • n={hoveredBar.n}
              </div>
            </div>
          )}

          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
            {/* Gridlines */}
            {[25, 50, 75, 100].map((val) => (
              <g key={val}>
                <line
                  x1={padding.left}
                  y1={scaleY(val)}
                  x2={width - padding.right}
                  y2={scaleY(val)}
                  stroke="#E2E8F0"
                  strokeDasharray="3 3"
                  strokeWidth="1"
                />
                <text
                  x={padding.left - 8}
                  y={scaleY(val) + 4}
                  textAnchor="end"
                  fontSize="11"
                  fill="#64748B"
                  fontFamily="JetBrains Mono"
                >
                  {val}%
                </text>
              </g>
            ))}

            {/* Bars & Error whiskers */}
            {data.map((item, i) => {
              const xCenter = padding.left + i * groupSpacing + groupSpacing / 2;
              const xBar = xCenter - barWidth / 2;
              const yBar = scaleY(item.value);
              const barH = plotHeight - (yBar - padding.top);

              const isHovered = hoveredBar?.label === item.label;
              const isHighlight = i < 2; // Top 2 groups highlighted per design spec

              const fillColor = isHighlight
                ? isHovered
                  ? '#4338CA'
                  : '#4F46E5'
                : isHovered
                ? '#94A3B8'
                : '#CBD5E1';

              // Error bar Y coords
              const yTop = scaleY(item.ci_upper);
              const yBottom = scaleY(item.ci_lower);

              return (
                <g
                  key={item.label}
                  className="cursor-pointer transition-all"
                  onMouseEnter={() =>
                    setHoveredBar({ ...item, x: xCenter, y: yBar })
                  }
                  onMouseLeave={() => setHoveredBar(null)}
                >
                  {/* Direct Numeric Label above bar */}
                  <text
                    x={xCenter}
                    y={yTop - 6}
                    textAnchor="middle"
                    fontSize="11"
                    fontWeight="600"
                    fill={isHighlight ? '#4F46E5' : '#475569'}
                    fontFamily="JetBrains Mono"
                  >
                    {item.value}%
                  </text>

                  {/* Rounded Top Bar */}
                  <rect
                    x={xBar}
                    y={yBar}
                    width={barWidth}
                    height={barH}
                    rx="6"
                    fill={fillColor}
                    className="transition-colors duration-200"
                  />

                  {/* 95% Confidence Interval Error Whisker */}
                  <line
                    x1={xCenter}
                    y1={yTop}
                    x2={xCenter}
                    y2={yBottom}
                    stroke="#0F172A"
                    strokeWidth="1.5"
                  />
                  <line
                    x1={xCenter - 8}
                    y1={yTop}
                    x2={xCenter + 8}
                    y2={yTop}
                    stroke="#0F172A"
                    strokeWidth="1.5"
                  />
                  <line
                    x1={xCenter - 8}
                    y1={yBottom}
                    x2={xCenter + 8}
                    y2={yBottom}
                    stroke="#0F172A"
                    strokeWidth="1.5"
                  />

                  {/* X Axis Label */}
                  <text
                    x={xCenter}
                    y={height - 15}
                    textAnchor="middle"
                    fontSize="12"
                    fontWeight="500"
                    fill="#334155"
                  >
                    {item.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-ink-muted px-1">
        <span>Whiskers show 95% Confidence Intervals</span>
        <span className="italic text-[11px]">Hover bar for cohort metadata</span>
      </div>
    </div>
  );
};

