import React from 'react';
import { Database, AlertCircle, FileSearch, ArrowRight } from 'lucide-react';
import './EmptyState.css';

export function EmptyState({
  icon: Icon = Database,
  title = 'No Data Available',
  description = 'No records match the current criteria or dataset ingestion is pending.',
  actionLabel,
  onAction,
  variant = 'compact', // 'compact', 'inline', 'default'
}) {
  return (
    <div className={`empty-state-card empty-state-${variant}`} role="region" aria-label={title}>
      <div className="empty-state-main">
        <div className="empty-state-icon-pill">
          <Icon size={16} className="empty-state-icon" />
        </div>
        <div className="empty-state-content">
          <h4 className="empty-state-title">{title}</h4>
          <p className="empty-state-description">{description}</p>
        </div>
      </div>
      {actionLabel && onAction && (
        <button
          type="button"
          className="btn btn-secondary btn-sm empty-state-btn"
          onClick={onAction}
        >
          <span>{actionLabel}</span>
          <ArrowRight size={12} />
        </button>
      )}
    </div>
  );
}
