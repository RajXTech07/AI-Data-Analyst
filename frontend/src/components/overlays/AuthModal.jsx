import React, { useState } from 'react';
import { X, Eye, EyeOff, Lock, Mail, UserCheck } from 'lucide-react';
import { Button } from '../common/Button';

/**
 * Sign-in Modal overlay adhering to DESIGN.md Section 4 & Section 6:
 * - Centered modal, 440px wide
 * - 16px rounded corners, soft larger shadow
 * - Tabs: "Sign in" and "Create account"
 * - Email, Password with show/hide toggle
 * - Primary button "Continue"
 * - "Signing in is optional. Sign in to keep your history."
 */
export const AuthModal = ({
  isOpen,
  onClose,
  onLogin,
  onRegister,
  currentUser = null,
  onLogout,
}) => {
  const [activeTab, setActiveTab] = useState('signin'); // 'signin' | 'register'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setIsLoading(true);

    try {
      if (activeTab === 'signin') {
        await onLogin(email || 'demo@local.dev', password || 'demopass123');
      } else {
        await onRegister(email, password, fullName);
      }
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Authentication failed. Please check credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUseDemo = async () => {
    setIsLoading(true);
    try {
      await onLogin('demo@local.dev', 'demopassword');
      onClose();
    } catch {
      // Fallback in case of offline backend
      onClose();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-ink-DEFAULT/40 backdrop-blur-xs transition-opacity animate-fade-in"
        onClick={onClose}
      />

      {/* Modal Card */}
      <div className="relative w-full max-w-[440px] bg-surface rounded-2xl shadow-modal border border-hairline p-6 z-10 animate-scale-up">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 text-ink-muted hover:text-ink rounded-lg transition-colors"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {currentUser ? (
          /* Signed In State */
          <div className="text-center py-4 space-y-4">
            <div className="w-12 h-12 rounded-full bg-primary-soft text-primary mx-auto flex items-center justify-center">
              <UserCheck className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-ink-strong">Signed In</h3>
              <p className="text-xs font-mono text-ink-muted mt-1">{currentUser.email}</p>
            </div>
            <div className="pt-2 flex flex-col gap-2">
              <Button
                variant="secondary"
                fullWidth
                onClick={() => {
                  onLogout && onLogout();
                  onClose();
                }}
              >
                Sign out
              </Button>
              <Button variant="text" onClick={onClose}>
                Back to analysis
              </Button>
            </div>
          </div>
        ) : (
          /* Sign In / Register Form */
          <>
            <div className="mb-5 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl overflow-hidden bg-white border border-hairline p-0.5 flex items-center justify-center shadow-xs shrink-0">
                <img src="/logo-icon.png" alt="DATA.ANALYTICS Logo" className="w-full h-full object-contain" />
              </div>
              <div className="flex flex-col text-left">
                <h2 className="text-lg font-bold text-ink-strong tracking-tight leading-tight">DATA.ANALYTICS</h2>
                <p className="text-xs text-ink-muted mt-0.5">
                  Keep your analysis history and verified reports synced.
                </p>
              </div>
            </div>

            {/* Segmented Tab Control */}
            <div className="flex p-1 bg-canvas rounded-xl border border-hairline mb-5">
              <button
                type="button"
                onClick={() => {
                  setActiveTab('signin');
                  setErrorMsg('');
                }}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  activeTab === 'signin'
                    ? 'bg-surface text-primary shadow-xs font-bold'
                    : 'text-ink-muted hover:text-ink'
                }`}
              >
                Sign in
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab('register');
                  setErrorMsg('');
                }}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  activeTab === 'register'
                    ? 'bg-surface text-primary shadow-xs font-bold'
                    : 'text-ink-muted hover:text-ink'
                }`}
              >
                Create account
              </button>
            </div>

            {errorMsg && (
              <div className="mb-4 p-3 rounded-lg bg-danger-soft border border-red-200 text-danger text-xs">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {activeTab === 'register' && (
                <div>
                  <label className="block text-xs font-semibold text-ink-strong mb-1">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Jane Doe"
                    className="w-full h-11 px-3.5 rounded-[10px] bg-surface border border-hairline text-sm text-ink-strong placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-ink-strong mb-1">
                  Email address
                </label>
                <div className="relative">
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="analyst@company.com"
                    className="w-full h-11 pl-10 pr-3.5 rounded-[10px] bg-surface border border-hairline text-sm text-ink-strong placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                  <Mail className="w-4 h-4 text-ink-muted absolute left-3.5 top-3.5" />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-ink-strong">Password</label>
                  {activeTab === 'signin' && (
                    <button
                      type="button"
                      onClick={() => alert('Password reset link sent in dev mode.')}
                      className="text-xs text-primary hover:underline"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full h-11 pl-10 pr-10 rounded-[10px] bg-surface border border-hairline text-sm text-ink-strong placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                  <Lock className="w-4 h-4 text-ink-muted absolute left-3.5 top-3.5" />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-3.5 text-ink-muted hover:text-ink"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="pt-2">
                <Button variant="primary" fullWidth type="submit" disabled={isLoading}>
                  {isLoading ? 'Processing...' : 'Continue'}
                </Button>
              </div>

              {/* Quick Demo Login Option */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={handleUseDemo}
                  className="w-full text-center py-2 text-xs font-semibold text-primary hover:bg-primary-soft rounded-lg transition-colors border border-dashed border-primary/40"
                >
                  ⚡ Quick Sign In as Demo Analyst
                </button>
              </div>

              <div className="pt-2 border-t border-hairline text-center">
                <p className="text-[12px] text-ink-muted">
                  Signing in is optional. Sign in to keep your history.
                </p>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
};

