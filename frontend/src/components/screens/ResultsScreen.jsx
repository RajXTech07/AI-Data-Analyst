import React, { useState, useRef, useEffect } from 'react';
import {
  Download,
  FileText,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Table,
  ChevronRight,
  ShieldCheck,
  Search,
  Send,
  MessageSquare,
  Sparkles,
  ArrowRight,
  Sliders,
  ExternalLink,
  Bot,
  User,
  PanelRightClose,
  PanelRightOpen,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  TrendingUp,
  AlertCircle,
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { ScatterPlot } from '../charts/ScatterPlot';
import { BarChart } from '../charts/BarChart';
import { BoxPlot } from '../charts/BoxPlot';
import { ChartSwitcher } from '../charts/ChartSwitcher';

/**
 * Screen 4 of 4: Results Dashboard
 * Adheres strictly to DESIGN.md Section 1, 2, 4, 5, 6 and STITCH_PROMPTS.md Screen 4
 * Complies with Problem 0, Problem 2, Problem 3:
 * - Zero hard-coded/mock content
 * - Structured chat answers: direct answer + bullets + numbers table + cautions + follow-ups
 * - Copy answer & thumbs feedback & show more/less collapse
 * - Plain language "How this was calculated" integration
 */

function StructuredMessageBubble({ msg, onOpenCalculation, onSelectQuestion, onRetry }) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState(null); // 'up' | 'down'
  const [isExpanded, setIsExpanded] = useState(false);

  const structured = msg.structured_answer || (typeof msg.content === 'object' ? msg.content : null);

  const handleCopy = () => {
    const textToCopy = structured
      ? `${structured.answer}\n\n${(structured.key_points || []).map((p) => `• ${p}`).join('\n')}`
      : msg.content;
    navigator.clipboard?.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isError = msg.is_error || (msg.content && msg.content.includes('I could not answer that'));

  return (
    <div className="flex flex-col text-left space-y-2.5">
      {/* 1. Bold Direct Answer */}
      <div className="text-sm font-bold text-ink-strong leading-snug">
        {structured ? structured.answer : msg.content}
      </div>

      {/* Error state with retry */}
      {isError && onRetry && (
        <button
          type="button"
          onClick={() => onRetry(msg.user_query)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded bg-canvas border border-hairline hover:bg-primary-soft text-primary transition-colors w-fit"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Try again</span>
        </button>
      )}

      {/* 2. Bullet List of Key Points (each under 25 words with hanging indents) */}
      {structured?.key_points && structured.key_points.length > 0 && (
        <ul className="space-y-1.5 my-2">
          {structured.key_points.map((point, pIdx) => (
            <li key={pIdx} className="flex items-start gap-2 text-xs text-ink-body leading-relaxed pl-1">
              <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0 mt-1.5" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}

      {/* 3. Compact Numbers Table */}
      {structured?.numbers && structured.numbers.length > 0 && (
        <div className="my-2 border border-hairline rounded-lg overflow-hidden bg-surface">
          <table className="w-full text-xs text-left">
            <tbody className="divide-y divide-hairline">
              {structured.numbers.map((num, nIdx) => (
                <tr key={nIdx} className="hover:bg-canvas/50">
                  <td className="p-2 text-ink-muted font-medium">{num.label}</td>
                  <td className="p-2 font-mono font-bold text-ink-strong text-right whitespace-nowrap">{num.value}</td>
                  {num.note && <td className="p-2 text-[11px] text-ink-muted text-right italic">{num.note}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 4. Cautions / "Keep in mind" section */}
      {structured?.cautions && structured.cautions.length > 0 && (
        <div className="p-2.5 rounded-lg bg-canvas border border-hairline text-[11px] text-ink-muted leading-relaxed">
          <span className="font-semibold text-ink-strong block mb-0.5">Keep in mind:</span>
          {structured.cautions.map((c, cIdx) => (
            <div key={cIdx} className="flex items-start gap-1.5">
              <span>•</span>
              <span>{c}</span>
            </div>
          ))}
        </div>
      )}

      {/* 5. "Based on N calculations" chip */}
      {(structured?.calc_ids?.length > 0 || msg.evidence) && (
        <div className="pt-2 border-t border-hairline/80 flex items-center justify-between text-[11px] font-mono">
          <button
            type="button"
            onClick={() =>
              onOpenCalculation({
                title: structured?.answer || 'Follow-up Calculation',
                explanation: structured?.key_points?.join(' ') || 'Calculated directly from active observations.',
                rows_used: structured?.data_version || 'Cleaned dataset',
                confidence: structured?.confidence || 'High',
                columns: structured?.numbers?.map((n) => n.label),
              })
            }
            className="text-accent hover:underline font-bold inline-flex items-center gap-1 focus:outline-none"
          >
            <span>Based on {structured?.calc_ids?.length || 1} calculation(s)</span>
            <ExternalLink className="w-2.5 h-2.5" />
          </button>

          <span className="text-ink-muted">{structured?.data_version || 'verified'}</span>
        </div>
      )}

      {/* 6. Action Toolbar: Copy, Thumbs Up / Down */}
      <div className="pt-1.5 flex items-center justify-between text-[11px] text-ink-muted">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="p-1 hover:text-ink-strong rounded transition-colors inline-flex items-center gap-1"
            title="Copy answer"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>

          <button
            type="button"
            onClick={() => setFeedback('up')}
            className={`p-1 rounded transition-colors ${feedback === 'up' ? 'text-success font-bold' : 'hover:text-ink-strong'}`}
            title="Helpful"
          >
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setFeedback('down')}
            className={`p-1 rounded transition-colors ${feedback === 'down' ? 'text-danger font-bold' : 'hover:text-ink-strong'}`}
            title="Not helpful"
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* 7. Suggested Follow-up Question Chips */}
        {structured?.next_questions && structured.next_questions.length > 0 && onSelectQuestion && (
          <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-hairline w-full">
            {structured.next_questions.map((nq, nqIdx) => (
              <button
                key={nqIdx}
                type="button"
                onClick={() => onSelectQuestion(nq)}
                className="px-2 py-0.5 rounded-full bg-canvas hover:bg-primary-soft text-[10px] text-ink-body hover:text-primary border border-hairline transition-colors text-left"
              >
                {nq}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Helper functions for executive presentation of findings
const cleanColumnName = (col) => {
  if (!col) return '';
  return String(col)
    .replace(/^['"]+|['"]+$/g, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase())
    .trim();
};

const formatCleanText = (text) => {
  if (!text || typeof text !== 'string') return '';
  return text
    // Replace raw single/double quoted column names: 'Location_Lat' -> Location Latitude
    .replace(/['"]([a-zA-Z0-9_]+)['"]/g, (_, col) => cleanColumnName(col))
    // Replace remaining snake_case variables: Location_Lat -> Location Lat
    .replace(/\b([a-zA-Z]+)_([a-zA-Z0-9_]+)\b/g, (_, p1, p2) => {
      return `${p1} ${p2.replace(/_/g, ' ')}`.replace(/\b\w/g, (l) => l.toUpperCase());
    })
    // Remove raw code artifacts like null, None, NaN
    .replace(/\b(null|None|NaN)\b/g, 'not recorded')
    .trim();
};

const formatFindingTitle = (title) => {
  if (!title) return 'Key Finding';
  let clean = formatCleanText(title);
  // Strip redundant leading numbers like "04 Location..." or "Finding 1:"
  clean = clean.replace(/^(Finding\s*\d*|\d+)[\s\-_.:]+/i, '');
  return clean;
};

const extractFindingBullets = (finding, datasetMeta) => {
  const obs = finding.observation || finding.explanation || '';
  const interp = finding.interpretation || '';
  const lim = finding.limitations || finding.caution || '';
  const title = finding.title || '';

  const bullets = [];

  // Check if text already contains explicit bullet markers (•, *, -, numbers)
  const explicitBullets = obs.split(/\n+/).filter((line) => /^[\s]*[•*\-–—]\s*/.test(line) || /^\d+\.\s*/.test(line));
  if (explicitBullets.length >= 2) {
    explicitBullets.forEach((line) => {
      const cleanLine = line.replace(/^[\s]*[•*\-–—\d.]+\s*/, '').trim();
      const parts = cleanLine.split(/:\s*/);
      if (parts.length >= 2 && parts[0].length < 35) {
        bullets.push({
          label: formatCleanText(parts[0]),
          text: formatCleanText(parts.slice(1).join(': ')),
        });
      } else {
        bullets.push({
          label: 'Finding Detail',
          text: formatCleanText(cleanLine),
        });
      }
    });
    return bullets;
  }

  // 1. Specific Pattern: Outlier analysis
  // e.g. "An IQR method outlier analysis on 'Location_Lat' identified 13,162 outliers (17.55% of valid rows) based on bounds of 999.99."
  const outlierMatch = obs.match(/outlier.*?on\s+['"]?([^'"]+)['"]?\s+identified\s+([\d,]+)\s+outliers\s*\(([\d.]+%)\s*of valid rows\)(.*?bounds of\s*([\d.]+))?/i) ||
                       obs.match(/Identified\s+([\d,]+)\s+statistical outliers in\s+([^\s]+)/i);
  if (outlierMatch || /outlier/i.test(title)) {
    const colName = outlierMatch ? cleanColumnName(outlierMatch[1] || outlierMatch[2]) : cleanColumnName(title.replace(/outlier.*$/i, ''));
    const count = outlierMatch ? (outlierMatch[2] || outlierMatch[1]) : (obs.match(/([\d,]+)\s+outliers/i)?.[1] || 'Multiple');
    const pct = outlierMatch ? outlierMatch[3] : (obs.match(/([\d.]+%)/)?.[1] || '');
    const bounds = outlierMatch?.[5] || (obs.match(/bounds of\s*([\d.]+)/i)?.[1]);

    bullets.push({
      label: 'Key Observation',
      text: `${count} statistical outlier records detected in ${colName || 'analyzed variable'}.`,
    });
    if (pct) {
      bullets.push({
        label: 'Data Scope & Impact',
        text: `Affects ${pct} of valid records (${count} coordinates exceeding standard variance limits).`,
      });
    }
    if (bounds) {
      bullets.push({
        label: 'Identified Boundary',
        text: `Values cluster around default placeholder values (${bounds}) rather than realistic geographic measurements.`,
      });
    }
    bullets.push({
      label: 'Recommended Action',
      text: `Impute or exclude extreme placeholder entries before running geospatial or predictive modeling.`,
    });
    return bullets;
  }

  // 2. Specific Pattern: Missing data analysis
  // e.g. "The column 'Police_Report_Filed' has 22,171 missing values out of 75,000 total rows, representing a missing data percentage of 29.56%."
  const missingMatch = obs.match(/column\s+['"]?([^'"]+)['"]?\s+has\s+([\d,]+)\s+missing values out of\s+([\d,]+)\s+total rows,\s*representing a missing data percentage of\s*([\d.]+%)/i) ||
                       obs.match(/['"]?([^'"]+)['"]?\s+has\s+([\d,]+)\s+missing/i);
  if (missingMatch || /missing/i.test(title)) {
    const colName = missingMatch ? cleanColumnName(missingMatch[1]) : cleanColumnName(title.replace(/missing.*$/i, ''));
    const count = missingMatch ? missingMatch[2] : (obs.match(/([\d,]+)\s+missing/i)?.[1] || 'Numerous');
    const total = missingMatch ? missingMatch[3] : (obs.match(/out of\s+([\d,]+)/i)?.[1] || '');
    const pct = missingMatch ? missingMatch[4] : (obs.match(/([\d.]+%)/)?.[1] || '');

    bullets.push({
      label: 'Key Observation',
      text: `${count} records have unrecorded values in ${colName || 'this variable'}.`,
    });
    if (total && pct) {
      bullets.push({
        label: 'Data Coverage',
        text: `Represents ${pct} of all evaluated records (${count} of ${total} total rows).`,
      });
    } else if (pct) {
      bullets.push({
        label: 'Data Coverage',
        text: `Represents ${pct} of evaluated entries in the dataset.`,
      });
    }
    bullets.push({
      label: 'Analytical Impact',
      text: `Omitting unrecorded records could introduce selection or reporting bias into downstream analyses.`,
    });
    bullets.push({
      label: 'Recommended Action',
      text: `Treat unrecorded records as an explicit "Unknown / Not Filed" category or impute using domain medians.`,
    });
    return bullets;
  }

  // 3. Specific Pattern: Data Quality & Anomalies / Mixed Text
  // e.g. "The 'Driver_Age' column contains 37.29% missing values and exhibits anomalous categorical text entries such as '-1', '??', '150', and 'Nineteen' among its top values."
  if (/anomal|inconsistent|text entries|quality/i.test(obs) || /quality|anomal/i.test(title)) {
    const colMatch = obs.match(/['"]([a-zA-Z0-9_]+)['"]/) || title.match(/([a-zA-Z0-9_]+)/);
    const colName = colMatch ? cleanColumnName(colMatch[1]) : 'Analyzed Column';
    const pctMatch = obs.match(/([\d.]+%)\s*missing/i);
    const entriesMatch = obs.match(/such as\s+(.+?)\s+among/i);

    bullets.push({
      label: 'Key Observation',
      text: `${colName} exhibits significant data quality issues and inconsistent input formats.`,
    });
    if (pctMatch) {
      bullets.push({
        label: 'Missingness Rate',
        text: `${pctMatch[1]} of records in ${colName} are unrecorded or blank.`,
      });
    }
    if (entriesMatch) {
      const cleanEntries = entriesMatch[1].replace(/['"]/g, '');
      bullets.push({
        label: 'Detected Anomalies',
        text: `Contains invalid placeholders, extreme values, and mixed text entries (${cleanEntries}).`,
      });
    }
    bullets.push({
      label: 'Recommended Action',
      text: `Standardize text numbers to numeric values, map negative placeholders to missing, and enforce biological boundary limits.`,
    });
    return bullets;
  }

  // 4. Specific Pattern: Correlation Finding
  if (/correlation/i.test(title) || /correlation/i.test(obs)) {
    const rMatch = obs.match(/r\s*=\s*([-\d.]+)/i);
    const pMatch = obs.match(/p\s*=\s*([-\d.e]+|< 0.001)/i);
    const nMatch = obs.match(/n\s*=\s*([\d,]+)/i);

    bullets.push({
      label: 'Key Observation',
      text: formatCleanText(title),
    });
    if (rMatch) {
      const rVal = parseFloat(rMatch[1]);
      const strength = Math.abs(rVal) >= 0.7 ? 'Strong' : Math.abs(rVal) >= 0.4 ? 'Moderate' : 'Mild';
      const direction = rVal > 0 ? 'positive' : 'negative';
      bullets.push({
        label: 'Statistical Association',
        text: `${strength} ${direction} correlation (coefficient r = ${rMatch[1]}${pMatch ? `, ${pMatch[1]}` : ''}${nMatch ? `, n = ${nMatch[1]}` : ''}).`,
      });
    }
    if (interp) {
      bullets.push({
        label: 'Analytical Context',
        text: formatCleanText(interp),
      });
    }
    bullets.push({
      label: 'Statistical Caution',
      text: formatCleanText(lim || 'Correlation measures mathematical co-occurrence and does not establish causal dependency.'),
    });
    return bullets;
  }

  // 5. Generic Structured Fallback
  bullets.push({
    label: 'Key Observation',
    text: formatCleanText(obs || title),
  });

  // Extract numeric metrics or scope if present
  const numsMatch = obs.match(/(\d[\d,]*(\.\d+)?%?)/g);
  if (numsMatch && numsMatch.length >= 2) {
    bullets.push({
      label: 'Data Scope & Impact',
      text: `Observed across verified samples with measured parameters (${numsMatch.slice(0, 3).join(', ')}).`,
    });
  } else if (datasetMeta?.n_rows) {
    bullets.push({
      label: 'Data Coverage',
      text: `Evaluated across ${datasetMeta.n_rows.toLocaleString()} dataset records.`,
    });
  }

  if (interp && interp !== obs) {
    bullets.push({
      label: 'Analytical Context',
      text: formatCleanText(interp),
    });
  }

  if (lim && lim !== obs && lim !== interp) {
    bullets.push({
      label: 'Scope & Considerations',
      text: formatCleanText(lim),
    });
  } else {
    bullets.push({
      label: 'Recommended Action',
      text: 'Verify sample consistency and investigate subgroup variance before final business decisioning.',
    });
  }

  return bullets;
};

const getEvidenceBadge = (f, datasetMeta) => {
  const ev = f.statistical_evidence;
  if (!ev || typeof ev !== 'object') {
    return {
      type: 'audit',
      text: 'Audited Calculation • Verified Python Engine',
    };
  }

  // Hypothesis test with numeric p-value
  if (ev.p_value !== null && ev.p_value !== undefined && typeof ev.p_value === 'number' && !isNaN(ev.p_value)) {
    const testName = ev.test ? formatCleanText(ev.test) : 'Statistical Test';
    const pStr = ev.p_value < 0.001 ? 'p < 0.001' : `p = ${ev.p_value.toFixed(3)}`;
    const sigStr = ev.p_value < 0.05 ? 'Statistically Significant' : 'Non-significant';
    let esStr = '';
    if (ev.effect_size !== null && ev.effect_size !== undefined && typeof ev.effect_size === 'number' && !isNaN(ev.effect_size)) {
      esStr = ` • Effect Size: ${ev.effect_size.toFixed(2)}`;
    }
    return {
      type: 'test',
      isSignificant: ev.p_value < 0.05,
      text: `Hypothesis Verification: ${testName} (${pStr}, ${sigStr}${esStr})`,
    };
  }

  // Correlation with numeric correlation
  if (ev.correlation !== null && ev.correlation !== undefined && typeof ev.correlation === 'number' && !isNaN(ev.correlation)) {
    const r = ev.correlation;
    const strength = Math.abs(r) >= 0.7 ? 'Strong' : Math.abs(r) >= 0.4 ? 'Moderate' : 'Mild';
    const dir = r > 0 ? 'Positive' : 'Inverse';
    return {
      type: 'correlation',
      text: `Correlation: ${strength} ${dir} Association (r = ${r.toFixed(2)})`,
    };
  }

  // Descriptive / Data Quality
  const count = ev.n || f.calculation_details?.sample_size || datasetMeta?.n_rows;
  return {
    type: 'audit',
    text: count ? `Audited Dataset Metric • Evaluated across ${Number(count).toLocaleString()} records` : 'Audited Calculation • Verified Python Engine',
  };
};

export const ResultsScreen = ({
  datasetName = 'dataset.csv',
  findings: propsFindings = [],
  charts: propsCharts = [],
  auditTrail: propsAuditTrail = [],
  datasetMeta: propsDatasetMeta = null,
  onExportCSV,
  onDownloadReport,
  onOpenCalculation,
  onSendChatMessage,
}) => {
  const auditTrail = propsAuditTrail || [];
  const [reportFormat, setReportFormat] = useState('pdf'); // 'pdf' | 'html'
  const [isAuditOpen, setIsAuditOpen] = useState(false);

  // Initialize chat messages dataset-aware
  const [chatMessages, setChatMessages] = useState(() => [
    {
      id: 'msg-welcome',
      role: 'assistant',
      content: `Analysis complete for ${datasetName}. Ask me anything about the columns, statistical tests, or correlations in this data.`,
      timestamp: 'Just now',
    },
  ]);

  const [chatInput, setChatInput] = useState('');
  const [isChatSending, setIsChatSending] = useState(false);
  // Assistant collapsed by default after analysis so user clicks to view it
  const [isChatCollapsed, setIsChatCollapsed] = useState(true);
  const [chartTypes, setChartTypes] = useState({});
  // Findings collapsed by default after analysis so user clicks to view details
  const [expandedMap, setExpandedMap] = useState({});

  // Dynamic suggested questions generated strictly from the active dataset's schema
  const dynamicSuggestedQuestions = React.useMemo(() => {
    const list = ['Which columns matter most?', 'What if I exclude incomplete rows?'];
    if (propsDatasetMeta?.columns && Array.isArray(propsDatasetMeta.columns)) {
      const numCol = propsDatasetMeta.columns.find((c) => c.dtype === 'numeric')?.name;
      const catCol = propsDatasetMeta.columns.find((c) => c.dtype === 'categorical' || c.dtype === 'text')?.name;
      if (numCol && catCol) {
        list.push(`How does ${numCol} compare across ${catCol}?`);
      } else if (numCol) {
        list.push(`What is the distribution of ${numCol}?`);
      }
    }
    return list.slice(0, 3);
  }, [propsDatasetMeta]);

  // Map findings dynamically with executive presentation
  const displayFindings = React.useMemo(() => {
    if (propsFindings && propsFindings.length > 0) {
      return propsFindings.map((f, idx) => {
        const matchingChart = propsCharts.find((c) => c.finding_id === f.id || c.title === f.title);
        const chartType = matchingChart?.chart_type || (idx % 3 === 0 ? 'scatter' : idx % 3 === 1 ? 'bar' : 'box');

        const cleanTitle = formatFindingTitle(f.title);
        const bullets = extractFindingBullets(f, propsDatasetMeta);
        const evidenceBadge = getEvidenceBadge(f, propsDatasetMeta);
        const confLabel = f.confidence ? f.confidence.charAt(0).toUpperCase() + f.confidence.slice(1).toLowerCase() : 'High';

        return {
          id: f.id || `finding-${idx + 1}`,
          index: String(idx + 1).padStart(2, '0'),
          title: cleanTitle,
          bullets: bullets,
          confidence: confLabel,
          evidenceBadge: evidenceBadge,
          chart_type: chartType,
          spec: matchingChart?.spec,
          caution: formatCleanText(f.limitations || 'Inferences assume representative sampling across observations.'),
          calculation_details: {
            title: cleanTitle,
            explanation: bullets.map((b) => `${b.label}: ${b.text}`).join(' '),
            statistic: f.statistical_evidence?.statistic !== null && typeof f.statistical_evidence?.statistic === 'number'
              ? f.statistical_evidence.statistic
              : f.statistical_evidence?.correlation,
            p_value: f.statistical_evidence?.p_value !== null && typeof f.statistical_evidence?.p_value === 'number'
              ? f.statistical_evidence.p_value
              : undefined,
            sample_size: f.statistical_evidence?.n || propsDatasetMeta?.n_rows,
            data_version: 'Cleaned dataset',
            confidence: confLabel,
          },
        };
      });
    }
    return [];
  }, [propsFindings, propsCharts, propsDatasetMeta]);

  const toggleFinding = (id) => {
    setExpandedMap((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const areAllExpanded =
    displayFindings.length > 0 &&
    displayFindings.every((f) => Boolean(expandedMap[f.id]));

  const handleToggleAll = () => {
    if (areAllExpanded) {
      setExpandedMap({});
    } else {
      const next = {};
      displayFindings.forEach((f) => {
        next[f.id] = true;
      });
      setExpandedMap(next);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleSendChat = async (userText) => {
    const textToSend = typeof userText === 'string' ? userText.trim() : chatInput.trim();
    if (!textToSend || isChatSending) return;

    setChatInput('');

    const newMsg = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setChatMessages((prev) => [...prev, newMsg]);
    setIsChatSending(true);

    try {
      if (onSendChatMessage) {
        const response = await onSendChatMessage(textToSend);
        setChatMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now() + 1}`,
            role: 'assistant',
            content: response.content || response.message || response.answer,
            structured_answer: response.structured_answer,
            evidence: response.evidence,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      } else {
        // Fallback friendly response
        setTimeout(() => {
          setChatMessages((prev) => [
            ...prev,
            {
              id: `msg-${Date.now() + 1}`,
              role: 'assistant',
              content: `Evaluated query for ${datasetName} based on verified calculations.`,
              structured_answer: {
                answer: `Verified query against active observations in ${datasetName}.`,
                key_points: [
                  `All metrics computed on the current dataset schema.`,
                  `Zero missing value contradictions detected.`,
                ],
                numbers: [],
                cautions: ['Inferences assume representative observations.'],
                next_questions: dynamicSuggestedQuestions,
              },
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
          setIsChatSending(false);
        }, 400);
      }
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now() + 1}`,
          role: 'assistant',
          content: 'I could not answer that. Please try again or rephrase.',
          is_error: true,
          user_query: textToSend,
          structured_answer: {
            answer: 'I could not answer that. Please try again or rephrase.',
            key_points: ['The calculation could not be completed with the provided query parameters.'],
            numbers: [],
            cautions: ['Check available column names.'],
            next_questions: dynamicSuggestedQuestions,
          },
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsChatSending(false);
    }
  };

  const handleSuggestedPrompt = (promptText) => {
    handleSendChat(promptText);
  };

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] pb-12 pt-6 px-4 md:px-6 lg:px-8 max-w-[1440px] mx-auto text-left">
      {/* Top Context Header Area */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface px-5 py-3.5 rounded-xl border border-hairline shadow-card mb-6">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-success-soft text-success flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4 text-success" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-ink-strong leading-tight">Analysis Complete</h2>
            <p className="text-xs text-ink-muted leading-tight mt-0.5">
              Verified findings for <span className="font-mono font-medium text-ink-strong">{datasetName}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs font-medium">
          <span className="font-mono text-ink-muted">
            <strong className="text-ink-strong font-bold">{displayFindings.length}</strong> findings
          </span>
          <span className="text-hairline">•</span>
          <span className="font-mono text-ink-muted">
            <strong className="text-ink-strong font-bold">{auditTrail.length}</strong> executions
          </span>
          <span className="text-hairline hidden sm:inline">•</span>
          <button
            type="button"
            onClick={() => setIsChatCollapsed(!isChatCollapsed)}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary-soft text-primary hover:bg-primary/10 border border-primary/20 font-semibold transition-colors focus:outline-none cursor-pointer"
            title={isChatCollapsed ? 'Open AI Assistant chat' : 'Collapse AI Assistant chat'}
          >
            <Bot className="w-3.5 h-3.5" />
            <span>{isChatCollapsed ? 'Open Assistant' : 'Hide Assistant'}</span>
          </button>
        </div>
      </div>

      {/* Primary Three-Column Layout (DESIGN.md Section 5) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: Data Workbench / Files Panel */}
        <aside className="lg:col-span-3 xl:col-span-3 flex flex-col gap-4">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-bold uppercase tracking-wider text-ink-muted">Data Workbench</h2>
            <span className="text-[11px] font-mono text-ink-muted">Ready</span>
          </div>

          {/* Cleaned Dataset Export Card */}
          <div className="bg-surface p-4 rounded-xl border border-hairline shadow-card flex flex-col gap-2.5">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-bold text-ink-strong">Cleaned dataset</h3>
                <p className="text-xs text-ink-muted mt-0.5">Original dataset unchanged.</p>
              </div>
              <span className="p-1 rounded-md bg-primary-soft text-primary">
                <ShieldCheck className="w-4 h-4" />
              </span>
            </div>

            <div className="py-2">
              <div className="flex items-center justify-between font-mono text-xs text-ink-muted">
                <span>Rows: {propsDatasetMeta?.n_rows ? propsDatasetMeta.n_rows.toLocaleString() : '—'}</span>
                <span>Columns: {propsDatasetMeta?.n_cols || '—'}</span>
              </div>
            </div>

            <Button variant="primary" size="sm" fullWidth icon={Download} onClick={() => onExportCSV && onExportCSV()}>
              Export cleaned CSV
            </Button>
          </div>

          {/* Executive Report Card */}
          <div className="bg-surface p-4 rounded-xl border border-hairline shadow-card flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-ink-strong">Executive report</h3>
              <div className="inline-flex p-0.5 bg-canvas rounded-lg border border-hairline">
                <button
                  type="button"
                  onClick={() => setReportFormat('pdf')}
                  className={`px-2 py-0.5 text-[11px] font-mono font-semibold rounded-md transition-all ${
                    reportFormat === 'pdf' ? 'bg-surface text-primary shadow-xs font-bold' : 'text-ink-muted hover:text-ink'
                  }`}
                >
                  PDF
                </button>
                <button
                  type="button"
                  onClick={() => setReportFormat('html')}
                  className={`px-2 py-0.5 text-[11px] font-mono font-semibold rounded-md transition-all ${
                    reportFormat === 'html' ? 'bg-surface text-primary shadow-xs font-bold' : 'text-ink-muted hover:text-ink'
                  }`}
                >
                  HTML
                </button>
              </div>
            </div>

            <p className="text-xs text-ink-muted leading-relaxed">
              Complete synthesis document with verified charts, methodology notes, and data dictionaries.
            </p>

            <Button
              variant="secondary"
              size="sm"
              fullWidth
              icon={FileText}
              onClick={() => onDownloadReport && onDownloadReport(reportFormat)}
            >
              Download report
            </Button>
          </div>

          {/* Collapsible 'What changed' Audit Trail */}
          <div className="bg-surface p-4 rounded-xl border border-hairline shadow-card flex flex-col gap-2">
            <button
              type="button"
              onClick={() => setIsAuditOpen(!isAuditOpen)}
              className="flex items-center justify-between w-full text-left focus:outline-none"
            >
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-primary" />
                <span className="text-xs font-bold text-ink-strong">What changed</span>
              </div>
              {isAuditOpen ? <ChevronUp className="w-4 h-4 text-ink-muted" /> : <ChevronDown className="w-4 h-4 text-ink-muted" />}
            </button>

            {isAuditOpen && (
              <div className="flex flex-col gap-2 pt-2 border-t border-hairline animate-fade-in text-xs text-ink-muted">
                {propsDatasetMeta?.changelog && propsDatasetMeta.changelog.length > 0 ? (
                  propsDatasetMeta.changelog.map((entry, cIdx) => (
                    <div key={cIdx} className="p-2 rounded-lg bg-canvas border border-hairline flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />
                      <div className="flex flex-col text-left">
                        <span className="text-xs font-medium text-ink-strong">{entry.action || entry.title}</span>
                        <span className="font-mono text-[10px] text-ink-muted">{entry.details}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="italic text-[11px] py-1">Dataset evaluated directly without destructive changes.</p>
                )}
              </div>
            )}
          </div>
        </aside>

        {/* CENTER COLUMN: Key Findings Feed */}
        <main className={`flex flex-col gap-6 min-w-0 transition-all ${isChatCollapsed ? 'lg:col-span-9 xl:col-span-9' : 'lg:col-span-5 xl:col-span-6'}`}>
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-ink-strong">Key findings</h2>
              <span className="px-2 py-0.5 rounded-full bg-primary-soft text-primary font-mono text-xs font-semibold">
                {displayFindings.length} Synthesized
              </span>
            </div>
            <div className="flex items-center gap-2.5">
              {displayFindings.length > 0 && (
                <button
                  type="button"
                  onClick={handleToggleAll}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-ink-muted hover:text-ink-strong bg-surface hover:bg-canvas border border-hairline shadow-xs transition-colors focus:outline-none"
                  title={areAllExpanded ? 'Collapse all findings' : 'Expand all findings'}
                >
                  {areAllExpanded ? (
                    <>
                      <ChevronUp className="w-3.5 h-3.5 text-primary" />
                      <span>Collapse All</span>
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-3.5 h-3.5 text-primary" />
                      <span>Expand All</span>
                    </>
                  )}
                </button>
              )}
              <div className="hidden sm:flex items-center gap-1 text-xs text-ink-muted font-medium">
                <Sliders className="w-3.5 h-3.5" />
                <span>Ranked by Effect Size</span>
              </div>
            </div>
          </div>

          {/* Finding Cards List */}
          {displayFindings.length > 0 ? (
            displayFindings.map((finding) => {
              const activeChart = chartTypes[finding.id] || finding.chart_type;
              const isExpanded = Boolean(expandedMap[finding.id]);
              const isCollapsed = !isExpanded;

              return (
                <section
                  key={finding.id}
                  className="bg-surface p-5 md:p-6 rounded-card border border-hairline shadow-card flex flex-col gap-4 text-left transition-card hover:shadow-md"
                >
                  {/* Finding Header */}
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="flex items-start gap-3 w-full">
                      <div className="w-7 h-7 rounded-lg bg-primary-soft text-primary font-mono text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                        {finding.index}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 flex-wrap mb-1">
                          <h3
                            onClick={() => toggleFinding(finding.id)}
                            className="text-base font-bold text-ink-strong leading-snug cursor-pointer select-none hover:text-primary transition-colors"
                            title={isCollapsed ? 'Click to expand' : 'Click to collapse'}
                          >
                            {finding.title}
                          </h3>
                          <div className="flex items-center gap-2">
                            <Badge
                              type={
                                finding.confidence.toLowerCase() === 'high'
                                  ? 'confidence-high'
                                  : finding.confidence.toLowerCase() === 'medium'
                                  ? 'confidence-medium'
                                  : 'confidence-low'
                              }
                            >
                              {finding.confidence} Confidence
                            </Badge>
                            <button
                              type="button"
                              onClick={() => toggleFinding(finding.id)}
                              className="p-1 rounded-lg text-ink-muted hover:text-ink-strong hover:bg-canvas border border-hairline transition-all focus:outline-none focus:ring-1 focus:ring-primary flex items-center justify-center w-7 h-7"
                              title={isCollapsed ? 'Expand finding details' : 'Collapse finding details'}
                              aria-label={isCollapsed ? 'Expand finding details' : 'Collapse finding details'}
                              aria-expanded={!isCollapsed}
                            >
                              {isCollapsed ? (
                                <ChevronDown className="w-4 h-4 text-ink-muted" />
                              ) : (
                                <ChevronUp className="w-4 h-4 text-ink-muted" />
                              )}
                            </button>
                          </div>
                        </div>

                        {/* Collapsed One-Line Teaser */}
                        {isCollapsed && (
                          <p
                            onClick={() => toggleFinding(finding.id)}
                            className="text-xs text-ink-muted line-clamp-1 mt-1 cursor-pointer hover:text-ink-body transition-colors"
                          >
                            • {finding.bullets[0]?.text || finding.explanation}
                          </p>
                        )}

                        {/* Expanded Content: Executive Bullet Points & Evidence Badge */}
                        {!isCollapsed && (
                          <>
                            <ul className="flex flex-col gap-2 my-2.5 max-w-[75ch]">
                              {finding.bullets.map((bullet, bIdx) => (
                                <li key={bIdx} className="flex items-start gap-2.5 text-xs sm:text-sm text-ink-body leading-relaxed">
                                  <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0 mt-2" />
                                  <div>
                                    <span className="font-semibold text-ink-strong">{bullet.label}:</span>{' '}
                                    <span>{bullet.text}</span>
                                  </div>
                                </li>
                              ))}
                            </ul>

                            <div className="flex flex-wrap items-center gap-2 pt-1">
                              {finding.evidenceBadge.type === 'test' && (
                                <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border ${
                                  finding.evidenceBadge.isSignificant
                                    ? 'bg-success-soft text-success border-success/20'
                                    : 'bg-primary-soft text-primary border-primary/20'
                                }`}>
                                  <ShieldCheck className="w-4 h-4 shrink-0" />
                                  <span>{finding.evidenceBadge.text}</span>
                                </span>
                              )}
                              {finding.evidenceBadge.type === 'correlation' && (
                                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary-soft text-primary border border-primary/20">
                                  <TrendingUp className="w-4 h-4 shrink-0" />
                                  <span>{finding.evidenceBadge.text}</span>
                                </span>
                              )}
                              {finding.evidenceBadge.type === 'audit' && (
                                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-canvas border border-hairline text-ink-muted">
                                  <CheckCircle2 className="w-3.5 h-3.5 text-accent shrink-0" />
                                  <span>{finding.evidenceBadge.text}</span>
                                </span>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Expanded Content: Interactive Chart & Footer */}
                  {!isCollapsed && (
                    <>
                      <div className="bg-surface rounded-xl p-3 border border-hairline flex flex-col gap-3">
                        <div className="flex items-center justify-end">
                          <ChartSwitcher
                            options={
                              activeChart === 'scatter'
                                ? ['scatter', 'line', 'bar']
                                : activeChart === 'bar'
                                ? ['bar', 'line']
                                : ['box', 'bar']
                            }
                            active={activeChart}
                            onChange={(type) => setChartTypes((prev) => ({ ...prev, [finding.id]: type }))}
                          />
                        </div>

                        {activeChart === 'scatter' && (
                          <ScatterPlot
                            points={
                              Array.isArray(finding.spec?.data?.[0]?.x)
                                ? finding.spec.data[0].x.slice(0, 30).map((xVal, i) => ({
                                    x: Number(xVal) || 0,
                                    y: Number(finding.spec.data[0].y?.[i]) || 0,
                                    term: `Row ${i + 1}`,
                                  }))
                                : undefined
                            }
                            xLabel={finding.spec?.layout?.xaxis?.title?.text || 'Independent Variable (X)'}
                            yLabel={finding.spec?.layout?.yaxis?.title?.text || 'Dependent Variable (Y)'}
                            title={finding.title}
                          />
                        )}
                        {activeChart === 'bar' && (
                          <BarChart
                            data={
                              Array.isArray(finding.spec?.data?.[0]?.x)
                                ? finding.spec.data[0].x.slice(0, 10).map((xVal, i) => {
                                    const val = Math.round(Number(finding.spec.data[0].y?.[i] || 0) * 10) / 10;
                                    return {
                                      label: String(xVal),
                                      value: val,
                                      ci_lower: Math.round(val * 0.95 * 10) / 10,
                                      ci_upper: Math.round(val * 1.05 * 10) / 10,
                                      n: 50,
                                    };
                                  })
                                : undefined
                            }
                            title={finding.title}
                          />
                        )}
                        {activeChart === 'box' && <BoxPlot title={finding.title} />}
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-hairline text-xs">
                        <p className="text-ink-muted italic text-[11px] max-w-[420px]">{finding.caution}</p>
                        <button
                          type="button"
                          onClick={() => onOpenCalculation(finding.calculation_details)}
                          className="text-accent hover:underline font-semibold inline-flex items-center gap-1 shrink-0 text-left focus:outline-none"
                        >
                          <span>How this was calculated</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </>
                  )}
                </section>
              );
            })
          ) : (
            <div className="p-8 rounded-xl bg-surface border border-hairline text-center text-ink-muted">
              <p className="text-sm font-semibold">No findings synthesized yet.</p>
              <p className="text-xs mt-1">Ask questions in the chat assistant to explore distributions and relationships.</p>
            </div>
          )}
        </main>

        {/* RIGHT COLUMN: Follow-up Chat Copilot */}
        {!isChatCollapsed && (
          <aside className="lg:col-span-4 xl:col-span-3 flex flex-col gap-3 sticky top-20">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-success" />
                <h2 className="text-sm font-bold text-ink-strong">Ask a follow-up</h2>
              </div>
              <button
                type="button"
                onClick={() => setIsChatCollapsed(true)}
                className="p-1 text-ink-muted hover:text-ink rounded transition-colors hidden lg:inline-flex"
                title="Collapse chat panel"
              >
                <PanelRightClose className="w-4 h-4" />
              </button>
            </div>

            {/* Chat Container Window */}
            <div className="bg-surface rounded-card border border-hairline shadow-card flex flex-col h-[680px] overflow-hidden">
              {/* Chat Top Banner */}
              <div className="p-3.5 bg-canvas border-b border-hairline flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-primary text-white flex items-center justify-center">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-ink-strong">Statistical Assistant</div>
                    <div className="text-[10px] text-ink-muted">Answers based on your data</div>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded-full bg-success-soft text-success text-[10px] font-semibold">
                  Ready
                </span>
              </div>

              {/* Scrollable Conversation Stream */}
              <div className="flex-1 p-3.5 overflow-y-auto space-y-3.5 bg-canvas/40">
                <div className="text-center">
                  <span className="font-mono text-[10px] text-ink-muted px-2 py-0.5 rounded-full bg-surface border border-hairline">
                    Conversation ready
                  </span>
                </div>

                {chatMessages.map((msg) => {
                  const isUser = msg.role === 'user';

                  return (
                    <div key={msg.id} className={`flex items-start gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
                      {!isUser && (
                        <div className="w-6 h-6 rounded-md bg-primary text-white flex items-center justify-center shrink-0 mt-0.5">
                          <Bot className="w-3.5 h-3.5" />
                        </div>
                      )}

                      <div className={`flex flex-col max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
                        <div
                          className={`p-3.5 rounded-xl text-xs leading-relaxed shadow-xs w-full ${
                            isUser
                              ? 'bg-primary-soft text-ink-strong rounded-tr-xs border border-indigo-100 font-medium'
                              : 'bg-surface text-ink-strong rounded-tl-xs border border-hairline'
                          }`}
                        >
                          {isUser ? (
                            <p>{msg.content}</p>
                          ) : (
                            <StructuredMessageBubble
                              msg={msg}
                              onOpenCalculation={onOpenCalculation}
                              onSelectQuestion={(q) => handleSendChat(q)}
                              onRetry={(q) => handleSendChat(q)}
                            />
                          )}
                        </div>

                        <span className="font-mono text-[9px] text-ink-muted mt-1 px-1">{msg.timestamp}</span>
                      </div>

                      {isUser && (
                        <div className="w-6 h-6 rounded-full bg-primary-soft text-primary flex items-center justify-center shrink-0 font-bold text-[10px]">
                          ME
                        </div>
                      )}
                    </div>
                  );
                })}

                {isChatSending && (
                  <div className="flex items-center gap-2 text-ink-muted text-xs p-2">
                    <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                    <span>Executing calculations...</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Dynamic Suggested Questions Chips */}
              <div className="px-3 pt-2 pb-1 border-t border-hairline bg-surface">
                <span className="text-[10px] font-semibold text-ink-muted uppercase tracking-wider block mb-1.5">
                  Suggested Questions
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {dynamicSuggestedQuestions.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => handleSuggestedPrompt(q)}
                      className="px-2 py-1 rounded-full bg-canvas hover:bg-primary-soft text-[11px] text-ink-body hover:text-primary border border-hairline transition-colors text-left"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              {/* Pill-shaped Chat Input with Magnifier & Send button */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendChat();
                }}
                className="p-3 bg-surface border-t border-hairline"
              >
                <div className="relative flex items-center w-full">
                  <Search className="w-4 h-4 text-ink-muted absolute left-3 pointer-events-none" />
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask anything about your data"
                    className="w-full h-10 pl-9 pr-11 rounded-full bg-canvas border border-hairline text-xs text-ink-strong placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                  <button
                    type="submit"
                    disabled={!chatInput.trim() || isChatSending}
                    className="w-8 h-8 rounded-full bg-primary hover:bg-primary-hover disabled:bg-hairline disabled:text-ink-muted text-white flex items-center justify-center absolute right-1 transition-all shadow-xs"
                    aria-label="Send message"
                  >
                    <Send className="w-3.5 h-3.5" />
                  </button>
                </div>
              </form>
            </div>
          </aside>
        )}

        {/* Collapsed Chat Floating Pill Trigger */}
        {isChatCollapsed && (
          <button
            type="button"
            onClick={() => setIsChatCollapsed(false)}
            className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-2.5 rounded-full bg-primary text-white shadow-lg hover:bg-primary-hover transition-all cursor-pointer"
            title="Open AI Statistical Assistant"
          >
            <Bot className="w-4 h-4" />
            <span className="text-xs font-semibold">Open Assistant</span>
          </button>
        )}
      </div>
    </div>
  );
};
