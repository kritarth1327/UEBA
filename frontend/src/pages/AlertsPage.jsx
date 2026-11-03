import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import {
  ShieldAlert,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  User,
  Calendar,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Save,
  X,
  FileCode,
  Shield,
  ArrowRight,
  RotateCcw,
} from 'lucide-react';
import { api } from '../api/client';
import { useDebounce } from '../hooks/useDebounce';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { Drawer } from '../components/Drawer';
import {
  formatDate,
  formatDateTime,
  formatRiskScore,
  getSeverityBadgeClass,
  getStatusBadgeClass,
} from '../utils/formatters';
import './AlertsPage.css';

export function AlertsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialSeverity = searchParams.get('severity') || '';
  const initialStatus = searchParams.get('status') || '';
  const initialSearch = searchParams.get('search') || '';
  const initialPage = parseInt(searchParams.get('page') || '1', 10);

  const [severity, setSeverity] = useState(initialSeverity);
  const [status, setStatus] = useState(initialStatus);
  const [searchInput, setSearchInput] = useState(initialSearch);
  const debouncedSearch = useDebounce(searchInput, 280);
  const [page, setPage] = useState(initialPage);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Selected Alert for Slide-Over Triage Drawer
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [newStatus, setNewStatus] = useState('');
  const [statusNotes, setStatusNotes] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateSuccess, setUpdateSuccess] = useState(null);
  const [updateError, setUpdateError] = useState(null);

  // Sync to URL parameters
  useEffect(() => {
    const params = new URLSearchParams();
    if (severity) params.set('severity', severity);
    if (status) params.set('status', status);
    if (debouncedSearch) params.set('search', debouncedSearch);
    if (page > 1) params.set('page', page.toString());
    setSearchParams(params, { replace: true });
  }, [severity, status, debouncedSearch, page, setSearchParams]);

  const fetchAlerts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getAlerts({
        page,
        page_size: 15,
        severity: severity || undefined,
        status: status || undefined,
        search: debouncedSearch || undefined,
      });
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to retrieve security incident queue.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [severity, status, debouncedSearch, page]);

  const openAlertDrawer = (alert) => {
    setSelectedAlert(alert);
    setNewStatus(alert.status);
    setStatusNotes(alert.notes || '');
    setUpdateSuccess(null);
    setUpdateError(null);
  };

  const closeAlertDrawer = () => {
    setSelectedAlert(null);
    setUpdateSuccess(null);
    setUpdateError(null);
  };

  const handleUpdateStatus = async (e) => {
    e.preventDefault();
    if (!selectedAlert) return;

    setIsUpdating(true);
    setUpdateSuccess(null);
    setUpdateError(null);

    try {
      const updated = await api.updateAlertStatus(selectedAlert.id, {
        status: newStatus,
        notes: statusNotes,
      });
      setSelectedAlert(updated);
      setUpdateSuccess(`Incident #${updated.id} status updated to ${updated.status}.`);
      fetchAlerts();
    } catch (err) {
      setUpdateError(err.message || 'Failed to persist status changes.');
    } finally {
      setIsUpdating(false);
    }
  };

  const clearFilters = () => {
    setSeverity('');
    setStatus('');
    setSearchInput('');
    setPage(1);
  };

  return (
    <div className="alerts-page">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Security Alert Triage Queue</h1>
          <p className="page-subtitle">
            Prioritized incidents generated from XGBoost threat classification, autoencoder anomalies, and baseline violations.
          </p>
        </div>

        <div className="alerts-queue-stat font-mono">
          <ShieldAlert size={14} className="text-amber" />
          <span>{data?.total ?? 0} Total Incidents in Queue</span>
        </div>
      </div>

      {/* Filter and Triage Bar */}
      <div className="card triage-filter-strip">
        <div className="triage-search-box">
          <Search size={14} className="search-ico text-muted" />
          <input
            type="text"
            className="triage-search-input"
            placeholder="Search incident reason, User ID, or employee name..."
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              setPage(1);
            }}
          />
          {searchInput && (
            <button
              type="button"
              className="clear-btn"
              onClick={() => {
                setSearchInput('');
                setPage(1);
              }}
            >
              <X size={13} />
            </button>
          )}
        </div>

        <div className="triage-controls-row">
          {/* Quick Severity Filter Tabs */}
          <div className="tab-group">
            <button
              type="button"
              className={`tab-btn ${!severity ? 'tab-btn-active' : ''}`}
              onClick={() => {
                setSeverity('');
                setPage(1);
              }}
            >
              All Severities
            </button>
            <button
              type="button"
              className={`tab-btn ${severity === 'CRITICAL' ? 'tab-btn-active' : ''}`}
              onClick={() => {
                setSeverity('CRITICAL');
                setPage(1);
              }}
            >
              Critical
            </button>
            <button
              type="button"
              className={`tab-btn ${severity === 'HIGH' ? 'tab-btn-active' : ''}`}
              onClick={() => {
                setSeverity('HIGH');
                setPage(1);
              }}
            >
              High
            </button>
            <button
              type="button"
              className={`tab-btn ${severity === 'MEDIUM' ? 'tab-btn-active' : ''}`}
              onClick={() => {
                setSeverity('MEDIUM');
                setPage(1);
              }}
            >
              Medium
            </button>
          </div>

          {/* Status Dropdown */}
          <select
            className="styled-select triage-status-select"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Statuses</option>
            <option value="OPEN">Open (Untriaged)</option>
            <option value="INVESTIGATING">Investigating</option>
            <option value="RESOLVED">Resolved</option>
            <option value="DISMISSED">Dismissed (Benign)</option>
          </select>

          {(severity || status || searchInput) && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={clearFilters}>
              Clear
            </button>
          )}
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={fetchAlerts} />}

      {loading ? (
        <LoadingSpinner message="Querying security alert repository..." />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title={severity || status || searchInput ? 'No Incidents Match Current Filters' : 'Incident Queue Clear'}
          description={
            severity || status || searchInput
              ? 'Try widening your severity or status parameters, or clear the search query.'
              : 'No alerts have been generated. Alerts are automatically triggered when hybrid threat scores or anomaly reconstruction errors exceed calibrated thresholds.'
          }
          actionLabel={severity || status || searchInput ? 'Clear Filters' : 'View Detection Engines'}
          onAction={severity || status || searchInput ? clearFilters : () => navigate('/models')}
          variant="compact"
        />
      ) : (
        <div className="card alerts-table-card">
          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Incident</th>
                  <th>Target Entity</th>
                  <th>Employee / Department</th>
                  <th>Detection Reason</th>
                  <th>Risk Score</th>
                  <th>Detected Timestamp</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((alert) => (
                  <tr
                    key={alert.id}
                    className="clickable-row"
                    onClick={() => openAlertDrawer(alert)}
                  >
                    <td>
                      <span className={`badge ${getSeverityBadgeClass(alert.severity)}`}>
                        {alert.severity}
                      </span>
                    </td>
                    <td className="font-mono text-muted">#{alert.id}</td>
                    <td>
                      <Link
                        to={`/users/${alert.user_id}`}
                        className="entity-link font-mono font-bold"
                        onClick={(e) => e.stopPropagation()}
                        title="Jump to User Investigation"
                      >
                        <span>{alert.user_id}</span>
                        <ExternalLink size={11} />
                      </Link>
                    </td>
                    <td>
                      <div className="emp-dept-cell">
                        <span className="emp-name text-primary font-medium">{alert.employee_name || '—'}</span>
                        <span className="emp-dept text-muted">{alert.department || '—'}</span>
                      </div>
                    </td>
                    <td className="alert-reason-cell" title={alert.reason}>
                      {alert.reason}
                    </td>
                    <td className="font-mono font-bold">{formatRiskScore(alert.risk_score)}</td>
                    <td className="text-muted font-mono">{formatDateTime(alert.detected_at)}</td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(alert.status)}`}>
                        {alert.status}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          openAlertDrawer(alert);
                        }}
                      >
                        Triage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data.total_pages > 1 && (
            <div className="pagination-bar">
              <span className="pagination-text text-muted font-mono">
                Showing {((data.page - 1) * data.page_size) + 1} &ndash; {Math.min(data.page * data.page_size, data.total)} of {data.total} alerts
              </span>
              <div className="pagination-controls">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={13} />
                  <span>Previous</span>
                </button>
                <span className="page-indicator font-mono">
                  {data.page} / {data.total_pages}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= data.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <span>Next</span>
                  <ChevronRight size={13} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Slide-Over Investigation & Triage Drawer */}
      <Drawer
        isOpen={Boolean(selectedAlert)}
        onClose={closeAlertDrawer}
        title={`Incident #${selectedAlert?.id} Triage Dossier`}
        subtitle={`Detected: ${formatDateTime(selectedAlert?.detected_at)}`}
        width={560}
      >
        {selectedAlert && (
          <div className="triage-drawer-content">
            {/* Header Badges */}
            <div className="drawer-badge-strip">
              <span className={`badge ${getSeverityBadgeClass(selectedAlert.severity)}`}>
                {selectedAlert.severity} Severity
              </span>
              <span className={`badge ${getStatusBadgeClass(selectedAlert.status)}`}>
                Status: {selectedAlert.status}
              </span>
              <span className="font-mono text-muted font-medium ml-auto">
                Risk: {formatRiskScore(selectedAlert.risk_score)}/100
              </span>
            </div>

            <h4 className="drawer-incident-reason">{selectedAlert.reason}</h4>

            {/* Entity Snapshot Card with Direct Jump */}
            <div className="drawer-entity-card">
              <div className="dec-header">
                <span className="dec-title">TARGET ENTITY</span>
                <Link
                  to={`/users/${selectedAlert.user_id}`}
                  className="btn btn-primary btn-sm dec-investigate-btn"
                  onClick={closeAlertDrawer}
                >
                  <span>Investigate User Dossier</span>
                  <ArrowRight size={12} />
                </Link>
              </div>
              <div className="dec-grid">
                <div className="dec-cell">
                  <span className="dec-key">User ID:</span>
                  <span className="dec-val font-mono font-bold text-teal">{selectedAlert.user_id}</span>
                </div>
                <div className="dec-cell">
                  <span className="dec-key">Employee:</span>
                  <span className="dec-val">{selectedAlert.employee_name || '—'}</span>
                </div>
                <div className="dec-cell">
                  <span className="dec-key">Department:</span>
                  <span className="dec-val">{selectedAlert.department || '—'}</span>
                </div>
                <div className="dec-cell">
                  <span className="dec-key">Incident Date:</span>
                  <span className="dec-val font-mono">{formatDate(selectedAlert.date)}</span>
                </div>
              </div>
            </div>

            {/* Evidence Telemetry JSON */}
            {selectedAlert.evidence && (
              <div className="drawer-evidence-block">
                <div className="deb-header">
                  <FileCode size={13} className="text-teal" />
                  <span className="deb-title">Trigger Telemetry & Evidence Payload</span>
                </div>
                <pre className="deb-code font-mono">
                  {JSON.stringify(selectedAlert.evidence, null, 2)}
                </pre>
              </div>
            )}

            {/* Triage Status Update Form */}
            <form onSubmit={handleUpdateStatus} className="drawer-triage-form">
              <h5 className="form-heading">SOC Incident Disposition</h5>

              {updateSuccess && (
                <div className="alert-feedback feedback-success">{updateSuccess}</div>
              )}
              {updateError && (
                <div className="alert-feedback feedback-error">{updateError}</div>
              )}

              <div className="form-field-group">
                <label className="field-lbl">Disposition Status:</label>
                <select
                  className="field-sel"
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                >
                  <option value="OPEN">OPEN • Untriaged / In Queue</option>
                  <option value="INVESTIGATING">INVESTIGATING • In Active SOC Review</option>
                  <option value="RESOLVED">RESOLVED • Remediated & Closed</option>
                  <option value="DISMISSED">DISMISSED • False Positive / Benign</option>
                </select>
              </div>

              <div className="form-field-group">
                <label className="field-lbl">SOC Investigation Notes:</label>
                <textarea
                  className="field-txt"
                  rows={3}
                  placeholder="Record SOC rationale, remediation actions, or verification findings..."
                  value={statusNotes}
                  onChange={(e) => setStatusNotes(e.target.value)}
                />
              </div>

              <div className="drawer-form-actions">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={closeAlertDrawer}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={isUpdating}
                >
                  <Save size={13} />
                  <span>{isUpdating ? 'Persisting...' : 'Persist Status'}</span>
                </button>
              </div>
            </form>
          </div>
        )}
      </Drawer>
    </div>
  );
}
