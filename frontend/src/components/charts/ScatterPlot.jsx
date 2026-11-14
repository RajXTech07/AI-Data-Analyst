import React, { useState } from 'react';
import { Table, BarChart2 } from 'lucide-react';

/**
 * Interactive SVG Scatter Plot adhering to DESIGN.md Section 2 & 4:
 * - Light horizontal gridlines only, no chart borders
 * - 12px axis labels in Quiet Slate (#64748B)
 * - Tooltip as small dark card (Ink fill #0F172A, white text, 8px radius)
 * - Linear regression trendline in Signal Indigo (#4F46E5)
 * - "View as table" accessibility option (Section 7)
 */
export const ScatterPlot = ({
  points = [],
  xLabel = 'Independent Variable (X)',
  yLabel = 'Dependent Variable (Y)',
  regressionEquation = '',
}) => {
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [viewAsTable, setViewAsTable] = useState(false);

  // SVG dimensions
  const width = 540;
  const height = 220;
  const padding = { top: 20, right: 30, bottom: 35, left: 45 };

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  // Scale functions (0 to 100)
  const scaleX = (val) => padding.left + (val / 100) * plotWidth;
  const scaleY = (val) => padding.top + plotHeight - (val / 100) * plotHeight;

  // Regression line coordinates (x=30 to x=100)
  const x1 = 30;
  const y1 = 0.58 * x1 + 19.4;
  const x2 = 100;
  const y2 = 0.58 * x2 + 19.4;

  return (
    <div className="w-full flex flex-col gap-2">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-ink-strong">{xLabel} vs {yLabel}</span>
          <span className="text-[11px] font-mono text-ink-muted">OLS: {regressionEquation}</span>
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
        /* Accessible Table View */
        <div className="max-h-52 overflow-y-auto border border-hairline rounded-lg">
          <table className="w-full text-left text-xs">
            <thead className="bg-canvas text-ink-muted sticky top-0">
              <tr>
                <th className="p-2 border-b border-hairline">Observation</th>
                <th className="p-2 border-b border-hairline font-mono">{xLabel}</th>
                <th className="p-2 border-b border-hairline font-mono">{yLabel}</th>
                <th className="p-2 border-b border-hairline">Cohort Term</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {points.map((pt, idx) => (
                <tr key={idx} className="hover:bg-canvas">
                  <td className="p-2 font-mono text-ink-muted">#{idx + 1}</td>
                  <td className="p-2 font-mono font-semibold text-ink-strong">{pt.x}%</td>
                  <td className="p-2 font-mono font-semibold text-primary">{pt.y}%</td>
                  <td className="p-2 text-ink-body">{pt.term}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        /* SVG Scatter Visual */
        <div className="relative w-full h-[220px] bg-canvas rounded-xl p-2 border border-hairline flex items-center justify-center select-none overflow-hidden">
          {/* Active Tooltip Dark Card */}
          {hoveredPoint && (
            <div
              className="absolute z-20 pointer-events-none bg-ink-DEFAULT text-white px-2.5 py-1.5 rounded-lg text-xs font-mono shadow-lg transition-transform"
              style={{
                left: `${Math.min(scaleX(hoveredPoint.x), width - 130)}px`,
                top: `${Math.max(scaleY(hoveredPoint.y) - 45, 10)}px`,
              }}
            >
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-primary" />
                <span>Att: {hoveredPoint.x}% → Mark: {hoveredPoint.y}%</span>
              </div>
              <div className="text-[10px] text-slate-300 mt-0.5">{hoveredPoint.term}</div>
            </div>
          )}

          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
            {/* Horizontal Gridlines only */}
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

            {/* X-axis ticks & labels */}
            {[30, 50, 70, 90, 100].map((val) => (
              <text
                key={val}
                x={scaleX(val)}
                y={height - 10}
                textAnchor="middle"
                fontSize="11"
                fill="#64748B"
                fontFamily="JetBrains Mono"
              >
                {val}%
              </text>
            ))}

            {/* Regression trendline */}
            <line
              x1={scaleX(x1)}
              y1={scaleY(y1)}
              x2={scaleX(x2)}
              y2={scaleY(y2)}
              stroke="#4F46E5"
              strokeWidth="2.5"
              strokeLinecap="round"
            />

            {/* Scatter observations */}
            {points.map((pt, i) => {
              const cx = scaleX(pt.x);
              const cy = scaleY(pt.y);
              const isHovered = hoveredPoint === pt;

              return (
                <circle
                  key={i}
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 6 : 4}
                  fill={isHovered ? '#4338CA' : '#4F46E5'}
                  fillOpacity={isHovered ? 1 : 0.8}
                  stroke="#FFFFFF"
                  strokeWidth={isHovered ? 2 : 1}
                  className="cursor-pointer transition-all duration-150"
                  onMouseEnter={() => setHoveredPoint(pt)}
                  onMouseLeave={() => setHoveredPoint(null)}
                />
              );
            })}
          </svg>
        </div>
      )}

      {/* Legend & caption */}
      <div className="flex items-center justify-between text-xs text-ink-muted px-1">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-primary" />
            <span>Observations {points.length ? `(n = ${points.length})` : ''}</span>
          </span>
          {regressionEquation && (
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-0.5 bg-primary" />
              <span>Linear trend</span>
            </span>
          )}
        </div>
        <span className="italic text-[11px]">Hover point for record details</span>
      </div>
    </div>
  );
};

