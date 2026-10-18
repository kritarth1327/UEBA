import React from 'react';
import { Database, AlertCircle, FileSearch } from 'lucide-react';
import './EmptyState.css';

export function EmptyState({
  icon: Icon = Database,
  title = 'No Data Available',
  description = 'No records match the current criteria or dataset ingestion is pending.',
  actionLabel,
  onAction,
}) {
  return (
    <div className="empty-state-card" role="region" aria-label={title}>
      <div className="empty-state-icon-wrapper">
        <Icon size={26} className="empty-state-icon" />
      </div>
      <h3 className="empty-state-title">{title}</h3>
      <p className="empty-state-description">{description}</p>
      {actionLabel && onAction && (
        <button type="button" className="btn btn-secondary btn-sm empty-state-btn" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
