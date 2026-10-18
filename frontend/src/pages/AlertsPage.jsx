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
} from 'lucide-react';
import { api } from '../api/client';
import { useDebounce } from '../hooks/useDebounce';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { Modal } from '../components/Modal';
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

  // Selected Alert for Detail Modal & Triage
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

  const openAlertModal = (alert) => {
    setSelectedAlert(alert);
    setNewStatus(alert.status);
    setStatusNotes(alert.notes || '');
    setUpdateSuccess(null);
    setUpdateError(null);
  };

  const closeAlertModal = () => {
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
      setUpdateSuccess(`Status successfully persisted to ${updated.status}.`);
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
      <div className="page-header">
        <div>
          <h1 className="page-title">Security Alert Investigation Queue</h1>
          <p className="page-subtitle">
            Prioritized incidents generated from ML threat scoring, ANN reconstruction anomalies, and personal baseline deviations.
          </p>
        </div>

        <div className="alerts-count-tag font-mono">
          <ShieldAlert size={14} className="text-amber" />
          <span>{data?.total ?? 0} Recorded Incidents</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card alerts-filter-bar">
        <div className="search-box">
          <Search size={15} className="search-icon text-muted" />
          <input
            type="text"
            className="search-field"
            placeholder="Search by User ID, employee name, or incident reason..."
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              setPage(1);
            }}
          />
          {searchInput && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={() => {
                setSearchInput('');
                setPage(1);
              }}
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div className="filter-dropdowns">
          <select
            className="styled-select"
            value={severity}
            onChange={(e) => {
              setSeverity(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <select
            className="styled-select"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="INVESTIGATING">Investigating</option>
            <option value="RESOLVED">Resolved</option>
            <option value="DISMISSED">Dismissed</option>
          </select>

          {(severity || status || searchInput) && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={clearFilters}>
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={fetchAlerts} />}

      {loading ? (
        <LoadingSpinner message="Querying incident database..." />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title={severity || status || searchInput ? 'No Matching Incidents Found' : 'Incident Queue Empty'}
          description={
            severity || status || searchInput
              ? 'No security alerts match your selected filters.'
              : 'No alerts have been generated. Alerts are automatically triggered when hybrid threat scores or anomaly reconstruction errors exceed calibrated thresholds.'
          }
          actionLabel={severity || status || searchInput ? 'Reset Filters' : 'Inspect Models'}
          onAction={severity || status || searchInput ? clearFilters : () => navigate('/models')}
        />
      ) : (
        <div className="card alerts-table-card">
          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Incident ID</th>
                  <th>Entity ID</th>
                  <th>Employee</th>
                  <th>Reason</th>
                  <th>Risk Score</th>
                  <th>Detected At</th>
                  <th>Status</th>
                  <th>Triage</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((alert) => (
                  <tr
                    key={alert.id}
                    className="clickable-row"
                    onClick={() => openAlertModal(alert)}
                  >
                    <td>
                      <span className={`badge ${getSeverityBadgeClass(alert.severity)}`}>
                        {alert.severity}
                      </span>
                    </td>
                    <td className="font-mono text-muted">#{alert.id}</td>
                    <td className="font-mono font-bold text-primary">{alert.user_id}</td>
                    <td>{alert.employee_name || '—'}</td>
                    <td className="cell-reason" title={alert.reason}>
                      {alert.reason}
                    </td>
                    <td className="font-mono font-bold">{formatRiskScore(alert.risk_score)}</td>
                    <td className="text-muted">{formatDateTime(alert.detected_at)}</td>
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
                          openAlertModal(alert);
                        }}
                      >
                        Inspect
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
                Showing {((data.page - 1) * data.page_size) + 1} &ndash; {Math.min(data.page * data.page_size, data.total)} of {data.total} incidents
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

      {/* Incident Dossier & Triage Modal */}
      <Modal
        isOpen={Boolean(selectedAlert)}
        onClose={closeAlertModal}
        title={`Security Incident Dossier #${selectedAlert?.id}`}
        maxWidth={660}
      >
        {selectedAlert && (
          <div className="alert-modal-content">
            <div className="modal-header-strip">
              <div className="modal-badges">
                <span className={`badge ${getSeverityBadgeClass(selectedAlert.severity)}`}>
                  {selectedAlert.severity} Severity
                </span>
                <span className={`badge ${getStatusBadgeClass(selectedAlert.status)}`}>
                  Status: {selectedAlert.status}
                </span>
              </div>
              <span className="font-mono text-muted font-medium">
                Detected: {formatDate(selectedAlert.date)}
              </span>
            </div>

            <h4 className="incident-title">{selectedAlert.reason}</h4>

            {/* Target Entity Box */}
            <div className="target-entity-box">
              <div className="target-cell">
                <span className="target-label">Target Entity</span>
                <Link
                  to={`/users/${selectedAlert.user_id}`}
                  className="target-link font-mono"
                  onClick={closeAlertModal}
                >
                  <span>{selectedAlert.user_id}</span>
                  <ExternalLink size={12} />
                </Link>
              </div>
              <div className="target-cell">
                <span className="target-label">Employee</span>
                <span className="target-val">{selectedAlert.employee_name || '—'}</span>
              </div>
              <div className="target-cell">
                <span className="target-label">Department</span>
                <span className="target-val">{selectedAlert.department || '—'}</span>
              </div>
              <div className="target-cell">
                <span className="target-label">Threat Score</span>
                <span className="target-val font-mono font-bold">
                  {formatRiskScore(selectedAlert.risk_score)}/100
                </span>
              </div>
            </div>

            {/* Telemetry Evidence JSON */}
            {selectedAlert.evidence && (
              <div className="evidence-box">
                <div className="evidence-header">
                  <FileCode size={14} className="text-teal" />
                  <span className="evidence-label">Detection Evidence & Trigger Traces</span>
                </div>
                <pre className="evidence-code font-mono">
                  {JSON.stringify(selectedAlert.evidence, null, 2)}
                </pre>
              </div>
            )}

            {/* Triage Update Form */}
            <form onSubmit={handleUpdateStatus} className="triage-form">
              <h5 className="triage-title">SOC Analyst Triage & Incident Resolution</h5>

              {updateSuccess && (
                <div className="form-feedback feedback-success">{updateSuccess}</div>
              )}
              {updateError && (
                <div className="form-feedback feedback-error">{updateError}</div>
              )}

              <div className="form-row">
                <label className="form-field-label">Investigation Disposition:</label>
                <select
                  className="form-field-select"
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                >
                  <option value="OPEN">OPEN &bull; Awaiting Initial Triage</option>
                  <option value="INVESTIGATING">INVESTIGATING &bull; In Active SOC Review</option>
                  <option value="RESOLVED">RESOLVED &bull; Incident Remediated & Closed</option>
                  <option value="DISMISSED">DISMISSED &bull; Benign / False Positive</option>
                </select>
              </div>

              <div className="form-row">
                <label className="form-field-label">Analyst Case Notes:</label>
                <textarea
                  className="form-field-textarea"
                  rows={3}
                  placeholder="Record SOC rationale, remediation steps, or verification findings..."
                  value={statusNotes}
                  onChange={(e) => setStatusNotes(e.target.value)}
                />
              </div>

              <div className="form-actions-row">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={closeAlertModal}
                >
                  Close
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={isUpdating}
                >
                  <Save size={13} />
                  <span>{isUpdating ? 'Saving...' : 'Persist Status Update'}</span>
                </button>
              </div>
            </form>
          </div>
        )}
      </Modal>
    </div>
  );
}
