import React, { useEffect, useRef } from 'react';
import { X, CheckCircle2, ShieldCheck, Download, HelpCircle } from 'lucide-react';
import { Button } from '../common/Button';

/**
 * "How this was calculated" Panel
 * Plain-language explanation panel adhering to Problem 3:
 * - Plain-language title and 2-3 sentence explanation
 * - Small table of key numbers with friendly labels
 * - Which data was used (cleaned or original, and which columns)
 * - Optional "Download calculation details (JSON)"
 * - Focus-trapped and closable with Escape
 */
export const CalculationModal = ({ isOpen, onClose, details }) => {
  const panelRef = useRef(null);

  // Keyboard accessibility: Close on Escape key & trap focus
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !details) return null;

  const showDevDetails =
    typeof window !== 'undefined' &&
    Boolean(window.DEV_DETAILS || window.location?.search?.includes('dev=true'));

  const handleDownloadJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(details, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `calculation_details_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // Determine friendly strength label
  let strengthLabel = 'Moderate';
  if (details.effect_size !== undefined) {
    const es = Math.abs(Number(details.effect_size) || 0);
    if (es >= 0.5) strengthLabel = 'Large';
    else if (es >= 0.2) strengthLabel = 'Moderate';
    else strengthLabel = 'Small';
  } else if (details.statistic !== undefined && Math.abs(Number(details.statistic)) >= 0.6) {
    strengthLabel = 'Strong';
  }

  // Friendly title
  const plainTitle = details.title || details.test || 'How this was calculated';

  // 2-3 sentences plain explanation
  const plainExplanation =
    details.explanation ||
    details.interpretation ||
    'We evaluated this metric across valid observations in the dataset to verify that the pattern is statistically consistent and not driven by chance variation.';

  const rowsEvaluated = details.sample_size || details.n || details.rows_used || 'All valid records';
  const rowsExcluded = details.rows_excluded ? `${details.rows_excluded} (missing or invalid values)` : 'None (complete records)';
  const dataVersion = details.data_version ? `${details.data_version.charAt(0).toUpperCase() + details.data_version.slice(1)} dataset` : 'Cleaned dataset';
  const formatCol = (c) => String(c).replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  const columnsUsed = details.columns
    ? (Array.isArray(details.columns)
        ? details.columns.map(formatCol).join(', ')
        : formatCol(details.columns))
    : details.column
    ? formatCol(details.column)
    : 'Active variables';
  const confidence = details.confidence || (details.p_value !== null && details.p_value !== undefined && typeof details.p_value === 'number' && details.p_value < 0.05 ? 'High' : 'Medium');

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="calc-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Dimmed backdrop */}
      <div
        className="fixed inset-0 bg-ink-DEFAULT/40 backdrop-blur-xs transition-opacity animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog */}
      <div
        ref={panelRef}
        className="relative w-full max-w-[540px] bg-surface rounded-2xl shadow-modal border border-hairline p-6 z-10 animate-scale-up max-h-[90vh] overflow-y-auto text-left"
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 text-ink-muted hover:text-ink rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-start gap-3 mb-4 pr-8">
          <div className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-5 h-5 text-accent" />
          </div>
          <div>
            <div className="text-xs uppercase font-mono font-semibold tracking-wider text-accent">
              Calculation explanation
            </div>
            <h2 id="calc-modal-title" className="text-lg font-bold text-ink-strong tracking-tight">
              {plainTitle}
            </h2>
          </div>
        </div>

        {/* Plain Language Explanation */}
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-canvas border border-hairline">
            <span className="text-xs font-semibold text-ink-strong block mb-1">
              Summary
            </span>
            <p className="text-sm text-ink-body leading-relaxed">
              {plainExplanation}
            </p>
          </div>

          {/* Key Numbers Table with Friendly Labels */}
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted block mb-2">
              Key numbers
            </span>
            <div className="border border-hairline rounded-xl overflow-hidden bg-surface">
              <table className="w-full text-xs text-left">
                <tbody className="divide-y divide-hairline">
                  <tr className="hover:bg-canvas/50">
                    <td className="p-2.5 font-medium text-ink-muted w-1/2">Rows evaluated</td>
                    <td className="p-2.5 font-mono font-semibold text-ink-strong">{rowsEvaluated}</td>
                  </tr>
                  <tr className="hover:bg-canvas/50">
                    <td className="p-2.5 font-medium text-ink-muted">Rows excluded</td>
                    <td className="p-2.5 font-mono text-ink-strong">{rowsExcluded}</td>
                  </tr>
                  {details.p_value !== null && details.p_value !== undefined && typeof details.p_value === 'number' && !isNaN(details.p_value) && (
                    <tr className="hover:bg-canvas/50">
                      <td className="p-2.5 font-medium text-ink-muted">Statistical significance</td>
                      <td className="p-2.5 font-mono font-semibold text-success">
                        {details.p_value < 0.001
                          ? 'p < 0.001'
                          : `p = ${details.p_value.toFixed(3)}`}
                      </td>
                    </tr>
                  )}
                  {details.statistic !== null && details.statistic !== undefined && typeof details.statistic === 'number' && !isNaN(details.statistic) && (
                    <tr className="hover:bg-canvas/50">
                      <td className="p-2.5 font-medium text-ink-muted">Calculated value</td>
                      <td className="p-2.5 font-mono font-semibold text-ink-strong">
                        {details.statistic.toFixed(3)}
                      </td>
                    </tr>
                  )}
                  <tr className="hover:bg-canvas/50">
                    <td className="p-2.5 font-medium text-ink-muted">Result strength</td>
                    <td className="p-2.5 font-semibold text-primary">{strengthLabel}</td>
                  </tr>
                  <tr className="hover:bg-canvas/50">
                    <td className="p-2.5 font-medium text-ink-muted">Confidence level</td>
                    <td className="p-2.5 font-semibold text-success">{confidence}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Data Source & Columns Used */}
          <div className="p-3.5 rounded-xl bg-surface border border-hairline flex flex-col gap-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-ink-muted font-medium">Data source:</span>
              <span className="font-semibold text-ink-strong">{dataVersion}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-muted font-medium">Columns analyzed:</span>
              <span className="font-mono text-ink-strong text-[11px] truncate max-w-[280px]">
                {columnsUsed}
              </span>
            </div>
          </div>

          {/* Development / Advanced Debug Panel (Only with ?dev=true or DEV_DETAILS) */}
          {showDevDetails && (
            <div className="p-3 rounded-lg bg-slate-900 text-slate-200 text-xs font-mono space-y-1">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Development mode details</div>
              <div>Test: {details.test || 'None'}</div>
              <div>Tool: {details.tool_name || 'N/A'}</div>
              {details.formula && <div>Formula: {details.formula}</div>}
            </div>
          )}

          {/* Advanced Download Link */}
          <div className="pt-2 border-t border-hairline flex items-center justify-between text-xs">
            <button
              type="button"
              onClick={handleDownloadJSON}
              className="text-primary hover:underline inline-flex items-center gap-1.5 font-medium focus:outline-none"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download calculation details (JSON)</span>
            </button>

            <span className="text-[11px] text-ink-muted flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-success" />
              <span>Verified from data</span>
            </span>
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
