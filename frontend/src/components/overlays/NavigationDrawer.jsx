import React from 'react';
import { X, Plus, Database, FileText, Trash2, CheckCircle, ExternalLink } from 'lucide-react';
import { Button } from '../common/Button';

/**
 * Navigation Drawer overlay adhering to DESIGN.md Section 4 & Section 5:
 * - 320px wide, white surface
 * - Slides over a dimmed overlay (Ink at 40%)
 * - New analysis primary button
 * - Recent datasets list
 * - Reports list
 * - Settings and danger text button "Delete all my data"
 */
export const NavigationDrawer = ({
  isOpen,
  onClose,
  onNewAnalysis,
  onSelectDataset,
  onDownloadReport,
  recentDatasets = [],
  savedReports = [],
  backendStatus = 'online',
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Dimmed backdrop */}
      <div
        className="fixed inset-0 bg-ink-DEFAULT/40 backdrop-blur-xs transition-opacity duration-200 animate-fade-in"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <aside className="relative w-80 max-w-[85vw] h-full bg-surface border-r border-hairline shadow-2xl flex flex-col z-10 animate-slide-right">
        {/* Drawer Header */}
        <div className="p-4 border-b border-hairline flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg overflow-hidden bg-white border border-hairline p-0.5 flex items-center justify-center shadow-xs shrink-0">
              <img src="/logo-icon.png" alt="Logo" className="w-full h-full object-contain" />
            </div>
            <div className="flex flex-col text-left">
              <span className="text-xs font-bold text-ink-strong tracking-tight">
                DATA.ANALYTICS
              </span>
              <span className="text-[10px] text-ink-muted">
                Workspace History
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-ink-muted hover:text-ink-strong rounded-lg hover:bg-canvas transition-colors"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Action: New Analysis */}
        <div className="p-4 border-b border-hairline">
          <Button
            variant="primary"
            fullWidth
            icon={Plus}
            onClick={() => {
              onNewAnalysis();
              onClose();
            }}
          >
            New analysis
          </Button>
        </div>

        {/* Scrollable lists */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Recent datasets */}
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                Recent datasets
              </span>
              <span className="text-[11px] font-mono text-ink-muted">{recentDatasets.length}</span>
            </div>
            <div className="space-y-1">
              {recentDatasets.map((ds) => (
                <button
                  key={ds.id}
                  type="button"
                  onClick={() => {
                    onSelectDataset && onSelectDataset(ds);
                    onClose();
                  }}
                  className="w-full text-left p-2.5 rounded-lg hover:bg-canvas transition-colors group flex items-start gap-2.5"
                >
                  <Database className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-mono font-medium text-ink-strong truncate group-hover:text-primary">
                      {ds.name}
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-ink-muted mt-0.5">
                      <span>{ds.rows}</span>
                      <span>•</span>
                      <span>{ds.date}</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Saved Reports */}
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                Reports
              </span>
              <span className="text-[11px] font-mono text-ink-muted">{savedReports.length}</span>
            </div>
            <div className="space-y-1">
              {savedReports.map((rep) => (
                <div
                  key={rep.id}
                  className="flex items-center justify-between p-2.5 rounded-lg hover:bg-canvas transition-colors group"
                >
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <FileText className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-ink-strong truncate">
                        {rep.title}
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-ink-muted mt-0.5">
                        <span className="font-mono">{rep.format}</span>
                        <span>•</span>
                        <span>{rep.size}</span>
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onDownloadReport && onDownloadReport(rep)}
                    className="p-1.5 text-ink-muted hover:text-accent rounded hover:bg-surface transition-colors"
                    title="Download report"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Backend Engine Health Indicator */}
          <div className="p-3 rounded-xl bg-canvas border border-hairline">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-ink-strong">Backend Engine</span>
              <span className="inline-flex items-center gap-1 text-[11px] font-mono text-success font-medium">
                <CheckCircle className="w-3 h-3 text-success" />
                {backendStatus === 'online' ? 'Connected' : 'Offline Mode'}
              </span>
            </div>
            <p className="text-[11px] text-ink-muted mt-1 leading-normal">
              All metrics verified by calculations on your dataset.
            </p>
          </div>
        </div>

        {/* Drawer Footer with Danger Action */}
        <div className="p-4 border-t border-hairline flex flex-col gap-2">
          <Button
            variant="danger-text"
            icon={Trash2}
            onClick={() => {
              if (window.confirm('Are you sure you want to delete all cached dataset sessions?')) {
                localStorage.clear();
                window.location.reload();
              }
            }}
          >
            Delete all my data
          </Button>
          <span className="text-[10px] text-ink-muted text-center">
            Your original files are always safe and unchanged.
          </span>
        </div>
      </aside>
    </div>
  );
};

