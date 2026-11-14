import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toastSuccess = useCallback((msg, duration) => addToast(msg, 'success', duration), [addToast]);
  const toastWarning = useCallback((msg, duration) => addToast(msg, 'warning', duration), [addToast]);
  const toastError = useCallback((msg, duration) => addToast(msg, 'danger', duration), [addToast]);
  const toastInfo = useCallback((msg, duration) => addToast(msg, 'info', duration), [addToast]);

  return (
    <ToastContext.Provider value={{ addToast, removeToast, toastSuccess, toastWarning, toastError, toastInfo }}>
      {children}
      {/* Toast Container bottom-right */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none max-w-sm w-full">
        {toasts.map((toast) => {
          let colorBar = 'bg-info';
          let icon = <Info className="w-5 h-5 text-info shrink-0" />;
          let bg = 'bg-white';

          if (toast.type === 'success') {
            colorBar = 'bg-success';
            icon = <CheckCircle2 className="w-5 h-5 text-success shrink-0" />;
          } else if (toast.type === 'warning') {
            colorBar = 'bg-warning';
            icon = <AlertTriangle className="w-5 h-5 text-warning shrink-0" />;
          } else if (toast.type === 'danger' || toast.type === 'error') {
            colorBar = 'bg-danger';
            icon = <AlertCircle className="w-5 h-5 text-danger shrink-0" />;
          }

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex items-center justify-between gap-3 p-3.5 rounded-[12px] ${bg} shadow-lg border border-hairline relative overflow-hidden transition-all animate-slide-up`}
            >
              <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${colorBar}`} />
              <div className="flex items-center gap-3 pl-1 text-sm text-ink-body font-medium">
                {icon}
                <span>{toast.message}</span>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-ink-muted hover:text-ink p-1 rounded-md transition-colors"
                aria-label="Dismiss toast"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

