import React from 'react';
import { Loader2 } from 'lucide-react';
import './LoadingSpinner.css';

export function LoadingSpinner({ message = 'Loading records...', size = 20 }) {
  return (
    <div className="loading-container" role="status" aria-live="polite">
      <Loader2 size={size} className="spinner-icon" />
      <span className="loading-message">{message}</span>
    </div>
  );
}
