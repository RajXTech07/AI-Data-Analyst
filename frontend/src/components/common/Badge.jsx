import React from 'react';

/**
 * Chip / Badge adhering to DESIGN.md:
 * - Pill-shaped (rounded-full)
 * - 24px tall (h-6)
 * - 12px text (text-xs)
 * - 600 weight
 * - Visual dot + plain text (never rely on color alone)
 */
export const Badge = ({
  children,
  type = 'neutral', // 'severity-high' | 'severity-medium' | 'severity-low' | 'confidence-high' | 'confidence-medium' | 'confidence-low' | 'accent' | 'neutral'
  className = '',
}) => {
  const styles = {
    'severity-high': {
      bg: 'bg-danger-soft text-danger border border-red-200',
      dot: 'bg-danger',
    },
    'severity-medium': {
      bg: 'bg-warning-soft text-warning border border-amber-200',
      dot: 'bg-warning',
    },
    'severity-low': {
      bg: 'bg-info-soft text-info border border-blue-200',
      dot: 'bg-info',
    },
    'confidence-high': {
      bg: 'bg-success-soft text-success border border-emerald-200',
      dot: 'bg-success',
    },
    'confidence-medium': {
      bg: 'bg-warning-soft text-warning border border-amber-200',
      dot: 'bg-warning',
    },
    'confidence-low': {
      bg: 'bg-slate-100 text-ink-muted border border-slate-200',
      dot: 'bg-slate-400',
    },
    accent: {
      bg: 'bg-accent-soft text-accent border border-teal-200',
      dot: 'bg-accent',
    },
    neutral: {
      bg: 'bg-slate-100 text-ink-muted border border-hairline',
      dot: 'bg-slate-400',
    },
  };

  const current = styles[type] || styles.neutral;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 h-6 rounded-full text-xs font-semibold select-none ${current.bg} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${current.dot} shrink-0`} />
      <span>{children}</span>
    </span>
  );
};

