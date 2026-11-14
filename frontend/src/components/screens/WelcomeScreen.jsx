import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  X,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  FolderOpen,
  FileText,
  AlertCircle,
  ExternalLink,
  Terminal,
  BarChart3,
} from 'lucide-react';
import { Button } from '../common/Button';

/**
 * Screen 1 of 4: Welcome and Upload
 * Adheres strictly to DESIGN.md Section 1, 2, 3, 4, 6 and STITCH_PROMPTS.md Screen 1
 */
export const WelcomeScreen = ({
  selectedFile,
  onFileSelect,
  onRemoveFile,
  onLoadSample,
  onEnter,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const fileInputRef = useRef(null);

  const validateAndSelect = (file) => {
    setErrorMessage('');
    if (!file) return;

    // Check extension
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setErrorMessage('Only CSV files are supported. Please select a valid CSV dataset.');
      return;
    }

    // Check size limit: 10 MB (10 * 1024 * 1024)
    const MAX_SIZE = 10 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
      setErrorMessage(`This file is ${sizeMB} MB. The maximum file limit is 10 MB.`);
      return;
    }

    onFileSelect(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelect(e.dataTransfer.files[0]);
    }
  };

  const handleBrowseClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] flex flex-col items-center justify-between py-12 px-4 md:px-6">
      {/* Background radial glow */}
      <div className="absolute top-16 left-1/2 -translate-x-1/2 w-[720px] h-[340px] bg-gradient-to-b from-primary-soft/60 via-canvas to-transparent blur-3xl pointer-events-none -z-10 rounded-full" />

      {/* Main Hero & Dropzone Container */}
      <div className="w-full max-w-[760px] mx-auto flex flex-col items-center text-center my-auto">
        {/* App Logo */}
        <div className="mb-5 flex flex-col items-center select-none">
          <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-2xl bg-white border border-hairline shadow-card p-2 flex items-center justify-center transition-transform hover:scale-105 duration-200">
            <img
              src="/logo-icon.png"
              alt="DATA.ANALYTICS"
              className="w-full h-full object-contain"
            />
          </div>
        </div>

        {/* Eyebrow */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-soft border border-indigo-100 mb-4 select-none">
          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          <span className="text-[12px] font-semibold text-primary uppercase tracking-[0.08em]">
            Let's analyze the world
          </span>
        </div>

        {/* Display Heading */}
        <h1 className="text-3xl sm:text-4xl lg:text-[40px] font-bold text-ink-strong tracking-[-0.02em] leading-[1.15] max-w-[680px]">
          Welcome to DATA.ANALYTICS
        </h1>

        {/* Plain-Language Subheading */}
        <p className="mt-3 text-base sm:text-lg text-ink leading-relaxed max-w-[620px]">
          Upload a CSV and get problems found, data cleaned, charts explained, and answers to your questions.
        </p>

        {/* Upload & Dropzone Area */}
        <div className="w-full max-w-[640px] mt-8 flex flex-col gap-4">
          {/* Error Banner if validation fails */}
          {errorMessage && (
            <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-danger-soft border border-red-200 text-left text-xs text-danger animate-shake">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1">
                <span className="font-bold">File Error: </span>
                <span>{errorMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => setErrorMessage('')}
                className="text-danger hover:text-red-900"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Large Drop Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleBrowseClick}
            className={`relative group w-full h-[220px] rounded-dropzone bg-canvas border-2 border-dashed transition-all duration-200 flex flex-col items-center justify-center p-6 text-center cursor-pointer select-none ${
              isDragging
                ? 'border-primary bg-primary-soft/50 shadow-md scale-[1.01]'
                : errorMessage
                ? 'border-danger bg-danger-soft/30'
                : 'border-hairline hover:border-primary hover:bg-surface hover:shadow-card'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  validateAndSelect(e.target.files[0]);
                }
              }}
              className="hidden"
            />

            <div
              className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3 transition-colors ${
                isDragging
                  ? 'bg-primary text-white'
                  : 'bg-surface border border-hairline text-primary group-hover:bg-primary-soft'
              }`}
            >
              <UploadCloud className="w-6 h-6" />
            </div>

            <p className="text-base font-semibold text-ink-strong tracking-tight">
              Upload CSV or dataset
            </p>
            <p className="text-xs text-ink-muted mt-1 max-w-xs">
              Drag and drop, or browse. CSV only, up to 10 MB.
            </p>

            <div className="mt-4">
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-[10px] bg-surface hover:bg-canvas text-xs font-semibold text-ink-strong border border-hairline shadow-xs transition-colors">
                <FolderOpen className="w-4 h-4 text-ink-muted" />
                Browse files
              </span>
            </div>
          </div>

          {/* File Selected State (Compact File Chip) */}
          {selectedFile ? (
            <div className="w-full bg-surface rounded-xl p-3.5 border border-hairline shadow-card flex items-center justify-between animate-fade-in">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-primary-soft text-primary flex items-center justify-center shrink-0">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div className="flex flex-col text-left min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-ink-strong truncate max-w-[280px]">
                      {selectedFile.name}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-canvas border border-hairline font-mono text-[10px] text-ink-muted uppercase">
                      CSV
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] font-mono text-ink-muted mt-0.5">
                    <span>{formatFileSize(selectedFile.size)}</span>
                    <span>•</span>
                    <span className="text-primary font-medium">
                      {selectedFile.rows ? `${selectedFile.rows.toLocaleString()} rows` : 'Ready to analyze'}
                    </span>
                    <span>•</span>
                    <span>{selectedFile.cols ? `${selectedFile.cols} columns` : 'CSV file'}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded-full bg-success-soft text-success text-[11px] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-success" />
                  Ready
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveFile();
                  }}
                  className="p-1 rounded-md text-ink-muted hover:text-danger hover:bg-danger-soft transition-colors"
                  aria-label="Remove attached file"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : null}

          {/* Enter Action Button & Sample Trigger */}
          <div className="w-full flex flex-col gap-2.5 mt-2">
            <Button
              variant="primary"
              size="lg"
              fullWidth
              disabled={!selectedFile}
              onClick={onEnter}
              icon={ArrowRight}
              iconPosition="right"
            >
              Enter Workbench
            </Button>

            <div className="flex items-center justify-center gap-1.5 pt-1 text-xs text-ink-muted">
              <span>No file?</span>
              <button
                type="button"
                onClick={onLoadSample}
                className="text-primary hover:text-primary-hover font-semibold inline-flex items-center gap-1 hover:underline focus:outline-none"
              >
                <span>Try a sample dataset</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        {/* Trust Pledge */}
        <div className="mt-8 pt-4 flex items-center justify-center gap-2 text-ink-muted text-xs">
          <ShieldCheck className="w-4 h-4 text-accent" />
          <span>Calculations run in code, not guessed. Your file can be deleted anytime.</span>
        </div>
      </div>

      {/* 3 Capability Micro-Cards at Bottom */}
      <div className="w-full max-w-[960px] grid grid-cols-1 md:grid-cols-3 gap-4 mt-12 pt-8 border-t border-hairline">
        <div className="bg-surface rounded-xl p-4 border border-hairline shadow-card flex flex-col gap-1.5 text-left">
          <div className="flex items-center gap-2 text-primary font-semibold text-xs">
            <CheckCircle2 className="w-4 h-4 text-primary" />
            <span>Data Quality Audit</span>
          </div>
          <p className="text-xs text-ink leading-relaxed">
            Automatic identification of missing indices, skewed outliers, and mixed column data types.
          </p>
        </div>

        <div className="bg-surface rounded-xl p-4 border border-hairline shadow-card flex flex-col gap-1.5 text-left">
          <div className="flex items-center gap-2 text-primary font-semibold text-xs">
            <Terminal className="w-4 h-4 text-primary" />
            <span>Audited Calculations</span>
          </div>
          <p className="text-xs text-ink leading-relaxed">
            Every statistic and metric is computed accurately with zero guesswork.
          </p>
        </div>

        <div className="bg-surface rounded-xl p-4 border border-hairline shadow-card flex flex-col gap-1.5 text-left">
          <div className="flex items-center gap-2 text-primary font-semibold text-xs">
            <BarChart3 className="w-4 h-4 text-primary" />
            <span>Statistical Narratives</span>
          </div>
          <p className="text-xs text-ink leading-relaxed">
            Chart trends distilled into natural language summaries ready for executive circulation.
          </p>
        </div>
      </div>
    </div>
  );
};

