import React, { useState } from 'react';
import {
  ChevronRight,
  Table,
  Columns,
  HelpCircle,
  Copy,
  TrendingUp,
  Calendar,
  Layers,
  Sparkles,
  ShieldCheck,
  Check,
  ArrowRight,
  Filter,
  Sliders,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  FileText,
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';

/**
 * Screen 3 of 4: Data Health Review (Problems found in your dataset)
 * Adheres strictly to DESIGN.md Section 1, 2, 4, 5, 6 and STITCH_PROMPTS.md Screen 3
 */
export const ReviewScreen = ({
  datasetName = 'dataset.csv',
  rowCount = 0,
  colCount = 0,
  issues: propsIssues = [],
  summary: propsSummary = null,
  integrityScore: propsIntegrityScore,
  qualityTier: propsQualityTier,
  onProceedToAnalysis,
}) => {
  const [issues, setIssues] = useState(() => propsIssues || []);
  const [activeCategory, setActiveCategory] = useState('everything'); // 'everything' | 'columns' | 'missing' | 'duplicates' | 'outliers' | 'range'
  const [expandedWhyIds, setExpandedWhyIds] = useState(() => {
    const firstId = propsIssues?.[0]?.id;
    return firstId ? new Set([firstId]) : new Set();
  });

  React.useEffect(() => {
    if (propsIssues) {
      setIssues(propsIssues);
      const firstId = propsIssues[0]?.id;
      if (firstId) setExpandedWhyIds(new Set([firstId]));
    }
  }, [propsIssues]);

  const summary = propsSummary || {
    columns: { count: colCount, breakdown: `${colCount} columns detected` },
    missing_values: { percentage: 0, affected_columns: 0 },
    duplicates: { count: 0, description: 'No duplicates found' },
    outliers: { count: 0, description: 'No extreme values found' },
    data_range: { span: 'Complete', label: 'All records profiled' },
  };
  const score = propsIntegrityScore !== undefined ? propsIntegrityScore : 100;
  const tier = propsQualityTier || (score >= 90 ? 'Operational' : score >= 70 ? 'Moderate' : 'Needs Review');

  // Toggle selection for a single issue
  const toggleIssue = (id) => {
    setIssues((prev) =>
      prev.map((item) => (item.id === id ? { ...item, selected: !item.selected } : item))
    );
  };

  // Toggle select all
  const areAllSelected = issues.length > 0 && issues.every((i) => i.selected);
  const toggleSelectAll = () => {
    const nextState = !areAllSelected;
    setIssues((prev) => prev.map((item) => ({ ...item, selected: nextState })));
  };

  // Select None
  const handleSelectNone = () => {
    setIssues((prev) => prev.map((item) => ({ ...item, selected: false })));
  };

  // Reset to default
  const handleReset = () => {
    setIssues(propsIssues || []);
  };

  // Toggle 'Why?' rationale expansion
  const toggleWhy = (id) => {
    setExpandedWhyIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Category definitions with icons
  const categoryMeta = React.useMemo(() => ({
    everything: { label: 'Everything', icon: Layers },
    structure: { label: 'Structure & Headers', icon: Table },
    missing: { label: 'Missing values', icon: HelpCircle },
    duplicates: { label: 'Duplicates', icon: Copy },
    formats: { label: 'Formats & Casing', icon: Sliders },
    invalid_values: { label: 'Invalid values', icon: AlertTriangle },
    outliers: { label: 'Outliers', icon: TrendingUp },
    categorical: { label: 'Categorical & Typos', icon: Sparkles },
    hygiene: { label: 'Text hygiene', icon: FileText },
    logic: { label: 'Logic & Chronology', icon: ShieldCheck },
    columns: { label: 'Columns', icon: Columns },
    time_series: { label: 'Time-series', icon: Calendar },
    range: { label: 'Data range', icon: Calendar },
  }), []);

  // Filter issues based on selected category
  const filteredIssues = issues.filter((item) => {
    if (activeCategory === 'everything') return true;
    if (activeCategory === 'columns') return item.category === 'columns' || item.category === 'structure';
    if (activeCategory === 'range') return item.category === 'time_series' || item.category === 'range' || item.category === 'logic';
    return item.category === activeCategory;
  });

  // Dynamic category list showing all categories with detected issues
  const categoriesList = React.useMemo(() => {
    const counts = {};
    for (const item of issues) {
      counts[item.category] = (counts[item.category] || 0) + 1;
    }
    const list = [{ id: 'everything', label: 'Everything', count: issues.length, icon: Layers }];
    for (const [catId, count] of Object.entries(counts)) {
      if (catId !== 'everything' && count > 0) {
        const meta = categoryMeta[catId] || { label: catId.replace(/_/g, ' '), icon: Layers };
        list.push({
          id: catId,
          label: meta.label,
          count,
          icon: meta.icon,
        });
      }
    }
    return list;
  }, [issues, categoryMeta]);

  const selectedCount = issues.filter((i) => i.selected).length;

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] pb-32 pt-6 px-4 md:px-6 lg:px-8 max-w-[1440px] mx-auto">
      {/* Top Meta Bar: Step indicator & Active File Pill */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        {/* Step Tracker Breadcrumb */}
        <nav aria-label="Pipeline Progress" className="flex items-center gap-1.5 text-xs font-semibold select-none">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface border border-hairline text-ink-muted">
            <span className="w-4 h-4 rounded-full bg-hairline flex items-center justify-center font-mono text-[10px]">
              1
            </span>
            <span>Upload</span>
          </div>
          <ChevronRight className="w-3.5 h-3.5 text-hairline" />
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary text-white shadow-xs font-bold">
            <span className="w-4 h-4 rounded-full bg-white/20 flex items-center justify-center font-mono text-[10px]">
              2
            </span>
            <span>Review Health</span>
          </div>
          <ChevronRight className="w-3.5 h-3.5 text-hairline" />
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface border border-hairline text-ink-muted opacity-60">
            <span className="w-4 h-4 rounded-full bg-hairline flex items-center justify-center font-mono text-[10px]">
              3
            </span>
            <span>Insights</span>
          </div>
        </nav>

        {/* Source Dataset Token */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-hairline shadow-xs">
          <Table className="w-4 h-4 text-primary" />
          <span className="font-mono text-xs font-semibold text-ink-strong">{datasetName}</span>
          <span className="text-hairline">•</span>
          <span className="font-mono text-[11px] text-ink-muted">{rowCount.toLocaleString()} rows</span>
          <span className="text-hairline">•</span>
          <span className="font-mono text-[11px] text-ink-muted">{colCount} columns</span>
          <span className="px-1.5 py-0.2 rounded bg-canvas border border-hairline text-[10px] font-mono text-ink-muted uppercase">
            UTF-8
          </span>
        </div>
      </div>

      {/* Primary Page Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="text-[11px] font-mono font-semibold uppercase tracking-wider text-primary">
              Heuristic Audit Complete
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-ink-strong tracking-tight">
            Problems found in your dataset
          </h1>
          <p className="text-sm text-ink-body max-w-3xl mt-1 leading-relaxed">
            Automated statistical profiling scanned {(rowCount * colCount).toLocaleString()} data cells for drift, anomalies, and structural defects. Choose recommended fixes below before advancing to synthesis.
          </p>
        </div>

        {/* Quick Stats Metric Micro-Card */}
        <div className="flex items-center gap-4 px-4 py-2.5 rounded-xl bg-surface border border-hairline shadow-card self-start lg:self-auto">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-semibold text-ink-muted">Integrity Score</span>
            <span className="font-mono text-xl font-bold text-primary">
              {score}<span className="text-xs font-normal text-ink-muted font-sans">/100</span>
            </span>
          </div>
          <div className="w-px h-8 bg-hairline" />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-semibold text-ink-muted">Quality Tier</span>
            <span className="text-xs font-bold text-accent">{tier}</span>
          </div>
        </div>
      </div>

      {/* 5 Summary Metric Filter Tiles */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5 mb-8">
        {/* Tile 1: Columns */}
        <button
          type="button"
          onClick={() => setActiveCategory(activeCategory === 'structure' || activeCategory === 'columns' ? 'everything' : 'structure')}
          className={`p-3.5 rounded-xl bg-surface border text-left transition-all relative flex flex-col justify-between ${
            activeCategory === 'structure' || activeCategory === 'columns'
              ? 'border-2 border-primary bg-primary-soft shadow-card'
              : 'border-hairline hover:border-slate-300 shadow-card'
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase font-semibold text-ink-muted">Schema Columns</span>
            <Columns className="w-4 h-4 text-ink-muted" />
          </div>
          <div className="font-mono text-2xl font-bold text-ink-strong mb-1">
            {summary.columns.count}
          </div>
          <div className="text-[11px] text-ink-muted truncate">
            {summary.columns.breakdown}
          </div>
        </button>

        {/* Tile 2: Missing Values */}
        <button
          type="button"
          onClick={() => setActiveCategory(activeCategory === 'missing' ? 'everything' : 'missing')}
          className={`p-3.5 rounded-xl bg-surface border text-left transition-all relative flex flex-col justify-between ${
            activeCategory === 'missing'
              ? 'border-2 border-primary bg-primary-soft shadow-card'
              : 'border-hairline hover:border-slate-300 shadow-card'
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase font-semibold text-ink-muted">Missing Values</span>
            <HelpCircle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="flex items-baseline gap-1.5 mb-1">
            <span className="font-mono text-2xl font-bold text-warning">
              {summary.missing_values.percentage}%
            </span>
            <span className="font-mono text-[11px] text-ink-muted">voids</span>
          </div>
          <div className="text-[11px] text-ink-muted truncate">
            {summary.missing_values.affected_columns} columns affected
          </div>
        </button>

        {/* Tile 3: Duplicates */}
        <button
          type="button"
          onClick={() => setActiveCategory(activeCategory === 'duplicates' ? 'everything' : 'duplicates')}
          className={`p-3.5 rounded-xl bg-surface border text-left transition-all relative flex flex-col justify-between ${
            activeCategory === 'duplicates'
              ? 'border-2 border-primary bg-primary-soft shadow-card'
              : 'border-hairline hover:border-slate-300 shadow-card'
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase font-semibold text-ink-muted">Duplicates</span>
            <Copy className="w-4 h-4 text-ink-muted" />
          </div>
          <div className="font-mono text-2xl font-bold text-ink-strong mb-1">
            {summary.duplicates.count}
          </div>
          <div className="text-[11px] text-ink-muted truncate">
            {summary.duplicates.description}
          </div>
        </button>

        {/* Tile 4: Outliers */}
        <button
          type="button"
          onClick={() => setActiveCategory(activeCategory === 'outliers' ? 'everything' : 'outliers')}
          className={`p-3.5 rounded-xl bg-surface border text-left transition-all relative flex flex-col justify-between ${
            activeCategory === 'outliers'
              ? 'border-2 border-primary bg-primary-soft shadow-card'
              : 'border-hairline hover:border-slate-300 shadow-card'
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase font-semibold text-ink-muted">Outliers</span>
            <TrendingUp className="w-4 h-4 text-danger" />
          </div>
          <div className="font-mono text-2xl font-bold text-danger mb-1">
            {summary.outliers.count}
          </div>
          <div className="text-[11px] text-ink-muted truncate">
            {summary.outliers.description}
          </div>
        </button>

        {/* Tile 5: Data Range */}
        <button
          type="button"
          onClick={() => setActiveCategory(activeCategory === 'time_series' || activeCategory === 'range' ? 'everything' : 'time_series')}
          className={`p-3.5 rounded-xl bg-surface border text-left transition-all relative flex flex-col justify-between col-span-2 md:col-span-1 ${
            activeCategory === 'time_series' || activeCategory === 'range'
              ? 'border-2 border-primary bg-primary-soft shadow-card'
              : 'border-hairline hover:border-slate-300 shadow-card'
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase font-semibold text-ink-muted">Coverage Span</span>
            <Calendar className="w-4 h-4 text-ink-muted" />
          </div>
          <div className="font-mono text-base font-bold text-ink-strong mb-1 truncate">
            {summary.data_range.span}
          </div>
          <div className="text-[11px] text-ink-muted truncate">
            {summary.data_range.label}
          </div>
        </button>
      </div>

      {/* Main Multi-Pane Workbench */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Category List (260px via lg:col-span-3) */}
        <aside className="lg:col-span-3 flex flex-col gap-2 bg-surface p-4 rounded-xl border border-hairline shadow-card">
          <div className="flex items-center justify-between pb-2 mb-1 border-b border-hairline">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Filter by Category
            </span>
            <span className="text-xs font-mono text-ink-muted">{issues.length} total</span>
          </div>

          <div className="space-y-1">
            {categoriesList.map((cat) => {
              const Icon = cat.icon;
              const isActive = activeCategory === cat.id;

              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setActiveCategory(cat.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-primary text-white shadow-xs'
                      : 'text-ink-strong hover:bg-canvas'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-ink-muted'}`} />
                    <span>{cat.label}</span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-full font-mono text-[10px] ${
                      isActive ? 'bg-white/20 text-white' : 'bg-canvas text-ink-muted'
                    }`}
                  >
                    {cat.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Action Context Card in Sidebar */}
          {issues.length > 0 && (
            <div className="mt-4 p-3 rounded-lg bg-canvas border border-hairline flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5 text-primary text-xs font-bold">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Recommended actions</span>
              </div>
              <p className="text-[11px] text-ink-body leading-normal">
                Applying selected fixes standardizes values without altering your original file.
              </p>
            </div>
          )}
        </aside>

        {/* Right Data Table Panel (lg:col-span-9) */}
        <main className="lg:col-span-9 flex flex-col bg-surface rounded-xl border border-hairline shadow-card overflow-hidden">
          {/* Table Header Functional Bar */}
          <div className="px-5 py-3.5 bg-canvas border-b border-hairline flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-bold text-ink-strong">Detected Irregularities</h2>
              <span className="px-2 py-0.5 rounded-full bg-surface border border-hairline font-mono text-[11px] text-ink-muted">
                {filteredIssues.length} of {issues.length} shown
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={toggleSelectAll}
                className="px-2.5 py-1 text-xs font-medium text-ink-body hover:bg-surface rounded border border-hairline transition-colors flex items-center gap-1"
              >
                <Check className="w-3.5 h-3.5 text-primary" />
                {areAllSelected ? 'Deselect All' : 'Select All'}
              </button>
            </div>
          </div>

          {/* High-Density Data Grid */}
          {filteredIssues.length === 0 ? (
            /* Empty State Frame per DESIGN.md Section 6 */
            <div className="py-16 px-6 text-center flex flex-col items-center justify-center">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-3 ${issues.length > 0 ? 'bg-primary-soft text-primary' : 'bg-success-soft text-success'}`}>
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-ink-strong">
                {issues.length > 0
                  ? `No problems found in "${categoryMeta[activeCategory]?.label || activeCategory}" category.`
                  : 'No problems found. Your data looks clean.'}
              </h3>
              <p className="text-xs text-ink-muted mt-1 max-w-sm">
                {issues.length > 0
                  ? `There are ${issues.length} detected issue(s) across other categories.`
                  : 'No anomalies detected in the selected category. You can proceed with full confidence.'}
              </p>
              {issues.length > 0 && (
                <button
                  type="button"
                  onClick={() => setActiveCategory('everything')}
                  className="mt-4 px-3.5 py-1.5 rounded-lg bg-primary text-white text-xs font-semibold hover:bg-primary-hover shadow-xs transition-colors"
                >
                  View all {issues.length} detected issues
                </button>
              )}
            </div>
          ) : (
            <div className="w-full overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-canvas/50 text-[11px] font-semibold uppercase tracking-wider text-ink-muted border-b border-hairline">
                    <th scope="col" className="py-3 pl-4 pr-2 w-10 text-center">
                      <input
                        type="checkbox"
                        checked={areAllSelected}
                        onChange={toggleSelectAll}
                        aria-label="Select all issues"
                        className="w-4 h-4 rounded text-primary focus:ring-primary accent-primary cursor-pointer"
                      />
                    </th>
                    <th scope="col" className="py-3 px-3">Severity</th>
                    <th scope="col" className="py-3 px-3">Column</th>
                    <th scope="col" className="py-3 px-3">What we found</th>
                    <th scope="col" className="py-3 px-3">Impact</th>
                    <th scope="col" className="py-3 px-3">Suggested fix</th>
                    <th scope="col" className="py-3 pr-4 pl-3 text-right">Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {filteredIssues.map((issue) => {
                    const isExpanded = expandedWhyIds.has(issue.id);
                    const severityType =
                      issue.severity === 'High'
                        ? 'severity-high'
                        : issue.severity === 'Medium'
                        ? 'severity-medium'
                        : 'severity-low';

                    return (
                      <React.Fragment key={issue.id}>
                        {/* Main Issue Row */}
                        <tr
                          className={`transition-colors ${
                            issue.selected ? 'bg-primary-soft/30 hover:bg-primary-soft/50' : 'hover:bg-canvas'
                          }`}
                        >
                          <td className="py-3.5 pl-4 pr-2 text-center align-top">
                            <input
                              type="checkbox"
                              checked={issue.selected}
                              onChange={() => toggleIssue(issue.id)}
                              aria-label={`Select ${issue.column} fix`}
                              className="w-4 h-4 rounded text-primary accent-primary cursor-pointer mt-1"
                            />
                          </td>
                          <td className="py-3.5 px-3 align-top whitespace-nowrap">
                            <Badge type={severityType}>{issue.severity}</Badge>
                          </td>
                          <td className="py-3.5 px-3 align-top whitespace-nowrap">
                            <code className="font-mono text-xs font-semibold text-primary bg-primary-soft px-1.5 py-0.5 rounded border border-indigo-100">
                              {issue.column}
                            </code>
                          </td>
                          <td className="py-3.5 px-3 align-top">
                            <div className="text-xs font-semibold text-ink-strong">{issue.issue}</div>
                            <div className="font-mono text-[11px] text-ink-muted mt-0.5">{issue.details}</div>
                          </td>
                          <td className="py-3.5 px-3 align-top whitespace-nowrap">
                            <span className="font-mono text-xs font-semibold text-ink-strong">
                              {issue.affected_rows.toLocaleString()} rows
                            </span>
                          </td>
                          <td className="py-3.5 px-3 align-top">
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-canvas border border-hairline text-xs font-semibold text-ink-strong">
                              {issue.suggested_fix}
                            </span>
                          </td>
                          <td className="py-3.5 pr-4 pl-3 align-top text-right whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => toggleWhy(issue.id)}
                              className="inline-flex items-center gap-1 text-xs font-bold text-primary hover:text-primary-hover transition-colors"
                            >
                              <span>Why?</span>
                              {isExpanded ? (
                                <ChevronUp className="w-3.5 h-3.5" />
                              ) : (
                                <ChevronDown className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </td>
                        </tr>

                        {/* Expandable Algorithmic Rationale Box */}
                        {isExpanded && (
                          <tr className="bg-canvas border-b border-hairline animate-fade-in">
                            <td colSpan={7} className="px-6 py-4">
                              <div className="bg-surface rounded-xl p-4 border border-hairline shadow-card flex flex-col md:flex-row items-start gap-4">
                                <div className="p-2 rounded-lg bg-primary-soft text-primary shrink-0">
                                  <Sparkles className="w-5 h-5" />
                                </div>
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs font-bold text-ink-strong">
                                      Why this is recommended
                                    </span>
                                    <span className="font-mono text-[10px] text-accent bg-accent-soft px-1.5 py-0.5 rounded border border-teal-200">
                                      Statistical rationale
                                    </span>
                                  </div>
                                  <p className="text-xs text-ink-body leading-relaxed max-w-[70ch]">
                                    {issue.why}
                                  </p>
                                </div>
                                <div className="flex items-center gap-2 self-end md:self-center">
                                  {issue.options &&
                                    issue.options.slice(0, 2).map((opt) => (
                                      <button
                                        key={opt}
                                        type="button"
                                        className="px-2.5 py-1 text-xs font-semibold text-primary hover:bg-primary-soft border border-hairline rounded transition-colors"
                                      >
                                        {opt}
                                      </button>
                                    ))}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Table Footer */}
          <div className="px-5 py-3 bg-canvas/60 border-t border-hairline flex items-center justify-between font-mono text-[11px] text-ink-muted">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-success" />
              <span>Verified against current dataset</span>
            </div>
            <div>{filteredIssues.length} issues listed</div>
          </div>
        </main>
      </div>

      {/* Sticky Bottom Action Bar (DESIGN.md Section 4 & 5) */}
      <aside
        aria-label="Action Toolbar"
        className="fixed bottom-0 left-0 right-0 z-30 bg-surface/95 backdrop-blur-md border-t border-hairline shadow-lg"
      >
        <div className="max-w-[1440px] mx-auto px-4 md:px-6 lg:px-8 py-3.5 flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Left: Status & Safety pledge */}
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <div className="w-8 h-8 rounded-full bg-primary-soft text-primary flex items-center justify-center shrink-0">
              <ShieldCheck className="w-5 h-5 text-primary" />
            </div>
            <div className="flex flex-col text-left">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-ink-strong">
                  {selectedCount} {selectedCount === 1 ? 'fix' : 'fixes'} selected.
                </span>
                <span className="text-xs text-ink-muted hidden sm:inline">
                  Your original file stays unchanged.
                </span>
              </div>
              <span className="font-mono text-[10px] text-ink-muted">
                Virtual non-destructive pipeline enabled
              </span>
            </div>
            <button
              type="button"
              onClick={handleSelectNone}
              className="ml-2 text-xs font-semibold text-ink-muted hover:text-ink-strong underline underline-offset-4 transition-colors"
            >
              Select none
            </button>
          </div>

          {/* Right: Proceed Action CTA */}
          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            <Button variant="secondary" onClick={handleReset} className="hidden sm:inline-flex">
              Reset Changes
            </Button>
            <Button
              variant="primary"
              size="lg"
              onClick={() => {
                if (onProceedToAnalysis) {
                  const selectedFixes = Array.from(
                    new Set(
                      issues
                        .filter((i) => i.selected)
                        .flatMap((i) => [i.id, i.fix_type].filter(Boolean))
                    )
                  );
                  onProceedToAnalysis(selectedFixes);
                }
              }}
              icon={ArrowRight}
              iconPosition="right"
              className="w-full sm:w-auto"
            >
              Analyse
            </Button>
          </div>
        </div>
      </aside>
    </div>
  );
};

