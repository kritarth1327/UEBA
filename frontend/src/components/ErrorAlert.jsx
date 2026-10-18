import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import './ErrorAlert.css';

export function ErrorAlert({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="error-alert-banner" role="alert">
      <div className="error-alert-content">
        <AlertTriangle size={18} className="error-alert-icon" />
        <span className="error-alert-text">{message}</span>
      </div>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-sm error-retry-btn" onClick={onRetry}>
          <RotateCcw size={13} />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}
