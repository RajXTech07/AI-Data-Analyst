import React, { useState } from 'react';
import { Table, BarChart2 } from 'lucide-react';

/**
 * Interactive SVG Box Plot adhering to DESIGN.md Section 2:
 * - Tukey's 1.5x IQR method
 * - Outlier points: danger with a ring (#B91C1C)
 * - Light horizontal gridlines, monospace ticks
 */
export const BoxPlot = ({
  q1 = 59.2,
  median = 68.5,
  q3 = 77.7,
  lowerFence = 31.4,
  upperFence = 96.2,
  outliers = [98.0, 98.5, 99.0, 99.5, 100.0],
  title = 'Distribution & Outlier Range (Tukey 1.5× IQR)',
}) => {
  const [hoveredTarget, setHoveredTarget] = useState(null);
  const [viewAsTable, setViewAsTable] = useState(false);

  const width = 540;
  const height = 140;
  const padding = { left: 40, right: 30, top: 20, bottom: 45 };

  const plotWidth = width - padding.left - padding.right;
  const scaleX = (val) => padding.left + (val / 100) * plotWidth;

  const yCenter = 50;
  const boxHeight = 44;

  return (
    <div className="w-full flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-ink-strong">{title}</span>
          <span className="text-[11px] font-mono text-danger font-semibold bg-danger-soft px-2 py-0.5 rounded-full">
            {outliers.length} records &gt; {upperFence}%
          </span>
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
        <div className="p-3 bg-canvas border border-hairline rounded-lg text-xs font-mono">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div>Lower Fence: <span className="font-bold text-ink-strong">{lowerFence}%</span></div>
            <div>Q1 (25th): <span className="font-bold text-ink-strong">{q1}%</span></div>
            <div>Median (50th): <span className="font-bold text-primary">{median}%</span></div>
            <div>Q3 (75th): <span className="font-bold text-ink-strong">{q3}%</span></div>
            <div>Upper Fence: <span className="font-bold text-warning">{upperFence}%</span></div>
            <div className="col-span-2">
              Outliers: <span className="font-bold text-danger">{outliers.join('%, ')}%</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="relative w-full h-[140px] bg-canvas rounded-xl p-2 border border-hairline flex items-center justify-center select-none overflow-hidden">
          {hoveredTarget && (
            <div
              className="absolute z-20 pointer-events-none bg-ink-DEFAULT text-white px-2.5 py-1.5 rounded-lg text-xs font-mono shadow-lg transition-transform"
              style={{
                left: `${Math.min(scaleX(hoveredTarget.val) - 40, width - 120)}px`,
                top: '10px',
              }}
            >
              <span className="font-bold">{hoveredTarget.label}: </span>
              <span>{hoveredTarget.val}%</span>
            </div>
          )}

          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
            {/* Ticks baseline */}
            <line
              x1={padding.left}
              y1={height - 25}
              x2={width - padding.right}
              y2={height - 25}
              stroke="#CBD5E1"
              strokeWidth="1.5"
            />

            {[0, 25, 50, 75, 100].map((t) => (
              <g key={t}>
                <line
                  x1={scaleX(t)}
                  y1={height - 30}
                  x2={scaleX(t)}
                  y2={height - 20}
                  stroke="#94A3B8"
                  strokeWidth="1"
                />
                <text
                  x={scaleX(t)}
                  y={height - 8}
                  textAnchor="middle"
                  fontSize="11"
                  fill="#64748B"
                  fontFamily="JetBrains Mono"
                >
                  {t}%
                </text>
              </g>
            ))}

            {/* Left Whisker */}
            <line
              x1={scaleX(lowerFence)}
              y1={yCenter}
              x2={scaleX(q1)}
              y2={yCenter}
              stroke="#64748B"
              strokeWidth="1.5"
            />
            <line
              x1={scaleX(lowerFence)}
              y1={yCenter - 12}
              x2={scaleX(lowerFence)}
              y2={yCenter + 12}
              stroke="#64748B"
              strokeWidth="1.5"
            />

            {/* Interquartile Box (Q1 to Q3) */}
            <rect
              x={scaleX(q1)}
              y={yCenter - boxHeight / 2}
              width={scaleX(q3) - scaleX(q1)}
              height={boxHeight}
              rx="4"
              fill="#EEF2FF"
              stroke="#4F46E5"
              strokeWidth="1.5"
              className="cursor-pointer hover:fill-primary-soft"
              onMouseEnter={() =>
                setHoveredTarget({ label: 'IQR (Q1–Q3)', val: `${q1}–${q3}` })
              }
              onMouseLeave={() => setHoveredTarget(null)}
            />

            {/* Median Line (Q2) */}
            <line
              x1={scaleX(median)}
              y1={yCenter - boxHeight / 2}
              x2={scaleX(median)}
              y2={yCenter + boxHeight / 2}
              stroke="#4F46E5"
              strokeWidth="3"
              className="cursor-pointer"
              onMouseEnter={() => setHoveredTarget({ label: 'Median (Q2)', val: median })}
              onMouseLeave={() => setHoveredTarget(null)}
            />

            {/* Right Whisker */}
            <line
              x1={scaleX(q3)}
              y1={yCenter}
              x2={scaleX(upperFence)}
              y2={yCenter}
              stroke="#64748B"
              strokeWidth="1.5"
            />
            <line
              x1={scaleX(upperFence)}
              y1={yCenter - 12}
              x2={scaleX(upperFence)}
              y2={yCenter + 12}
              stroke="#64748B"
              strokeWidth="1.5"
            />

            {/* Tukey Fence Threshold Indicator */}
            <line
              x1={scaleX(upperFence)}
              y1={yCenter - 22}
              x2={scaleX(upperFence)}
              y2={yCenter + 22}
              stroke="#B45309"
              strokeWidth="1.5"
              strokeDasharray="3 3"
            />

            {/* Outlier Points (Danger with ring per DESIGN.md Section 2) */}
            {outliers.map((val, idx) => {
              const cx = scaleX(val);
              const cy = yCenter + ((idx % 3) - 1) * 8; // Slight vertical jitter for overlapping points

              return (
                <g
                  key={idx}
                  className="cursor-pointer"
                  onMouseEnter={() =>
                    setHoveredTarget({ label: `Outlier #${idx + 1}`, val })
                  }
                  onMouseLeave={() => setHoveredTarget(null)}
                >
                  {/* Outer danger ring */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r="6.5"
                    fill="none"
                    stroke="#B91C1C"
                    strokeWidth="1.5"
                    strokeOpacity="0.4"
                  />
                  {/* Inner danger dot */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r="4"
                    fill="#B91C1C"
                    stroke="#FFFFFF"
                    strokeWidth="1"
                  />
                </g>
              );
            })}
          </svg>
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-ink-muted px-1">
        <span>Tukey 1.5× IQR fence at {upperFence}%</span>
        <span className="italic text-[11px]">Red rings indicate flagged outliers</span>
      </div>
    </div>
  );
};

