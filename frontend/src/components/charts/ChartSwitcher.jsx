import React from 'react';

/**
 * Segmented chart-type switcher adhering to DESIGN.md Section 4:
 * "chart-type switcher as a small segmented control."
 */
export const ChartSwitcher = ({
  options = ['scatter', 'line', 'bar'],
  active = 'scatter',
  onChange,
}) => {
  const labels = {
    scatter: 'Scatter',
    line: 'Line',
    bar: 'Bar',
    box: 'Box Plot',
  };

  return (
    <div className="inline-flex p-0.5 bg-canvas rounded-lg border border-hairline select-none">
      {options.map((opt) => {
        const isSelected = active === opt;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange && onChange(opt)}
            className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
              isSelected
                ? 'bg-surface text-primary shadow-xs font-bold'
                : 'text-ink-muted hover:text-ink hover:bg-surface/50'
            }`}
          >
            {labels[opt] || opt}
          </button>
        );
      })}
    </div>
  );
};

