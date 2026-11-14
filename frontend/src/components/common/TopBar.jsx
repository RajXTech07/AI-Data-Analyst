import React from 'react';
import { Sparkles, Moon, Sun, Plus, Table, User } from 'lucide-react';

/**
 * Clean, modern TopBar:
 * - Brand wordmark on left
 * - Active dataset pill in the center when a file is loaded
 * - Sign in / user account button, "New Analysis" quick action, and Theme toggle on right
 * - Distraction-free, clean and modern SaaS layout
 */
export const TopBar = ({
  currentScreen = 'welcome', // 'welcome' | 'loading' | 'review' | 'results'
  activeDataset = null,
  onNavigateHome,
  onNewAnalysis,
  user = null,
  onOpenAuth,
  isDarkMode = false,
  onToggleDarkMode,
}) => {
  const isAnalyzing = currentScreen === 'review' || currentScreen === 'results';

  return (
    <header className="sticky top-0 z-40 w-full h-16 bg-surface/90 backdrop-blur-md border-b border-hairline transition-colors">
      <div className="max-w-[1440px] h-full mx-auto px-4 md:px-6 lg:px-8 flex items-center justify-between gap-4">
        {/* Left: Clean Brand */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onNavigateHome}
            className="flex items-center gap-2.5 text-left group focus:outline-none"
            title="Return to upload"
          >
            <div className="w-9 h-9 rounded-xl overflow-hidden bg-white border border-hairline flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform p-0.5 shrink-0">
              <img
                src="/logo-icon.png"
                alt="DATA.ANALYTICS Logo"
                className="w-full h-full object-contain"
              />
            </div>
            <div className="flex flex-col text-left">
              <span className="font-bold text-ink-strong tracking-tight text-[15px] leading-tight">
                DATA.ANALYTICS
              </span>
              <span className="text-[10px] text-ink-muted font-medium tracking-tight">
                AI Data Analyst
              </span>
            </div>
          </button>
        </div>

        {/* Center: Active Dataset Context (Only when loaded) */}
        {isAnalyzing && activeDataset && (
          <div className="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-canvas border border-hairline shadow-xs">
            <Table className="w-3.5 h-3.5 text-primary" />
            <span className="font-mono text-xs font-semibold text-ink-strong truncate max-w-[200px] lg:max-w-[320px]">
              {activeDataset.filename || 'dataset.csv'}
            </span>
            {activeDataset.n_rows && (
              <>
                <span className="text-ink-muted text-xs">•</span>
                <span className="font-mono text-[11px] text-ink-muted">
                  {activeDataset.n_rows.toLocaleString()} rows
                </span>
              </>
            )}
          </div>
        )}

        {/* Right: Sign in + New Analysis CTA + Theme Switcher */}
        <div className="flex items-center gap-3">
          {/* Sign in / User Account Option */}
          <button
            type="button"
            onClick={onOpenAuth}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-hairline bg-surface hover:bg-canvas text-ink-strong transition-all focus:outline-none focus:ring-2 focus:ring-primary shadow-xs"
            title={user ? `Signed in as ${user.email}` : 'Sign in to account'}
          >
            <div className="w-6 h-6 rounded-full bg-primary-soft text-primary flex items-center justify-center font-semibold text-xs">
              {user ? (
                user.email?.charAt(0)?.toUpperCase() || 'U'
              ) : (
                <User className="w-3.5 h-3.5 text-primary" />
              )}
            </div>
            <span className="text-xs font-semibold text-ink-strong hidden sm:inline">
              {user ? (user.full_name || user.email.split('@')[0]) : 'Sign in'}
            </span>
          </button>

          {/* Quick Action: Start New Analysis */}
          {isAnalyzing && onNewAnalysis && (
            <button
              type="button"
              onClick={onNewAnalysis}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-ink-strong bg-canvas hover:bg-surface border border-hairline hover:border-primary/40 transition-all shadow-xs focus:outline-none"
              title="Upload and analyze another dataset"
            >
              <Plus className="w-3.5 h-3.5 text-primary" />
              <span>New Analysis</span>
            </button>
          )}

          {/* Theme Switcher */}
          {onToggleDarkMode && (
            <button
              type="button"
              onClick={onToggleDarkMode}
              className="p-2 text-ink-muted hover:text-ink-strong hover:bg-canvas rounded-lg transition-colors border border-transparent hover:border-hairline"
              aria-label="Toggle dark mode"
              title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
