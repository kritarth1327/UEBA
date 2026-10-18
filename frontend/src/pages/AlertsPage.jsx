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
  const debouncedSearch = useDebounce(searchInput, 300);
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

  // Sync to URL query params
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
      setError(err.message || 'Failed to retrieve alert records.');
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

      // Refresh list to update badge and timestamps
      fetchAlerts();
    } catch (err) {
      setUpdateError(err.message || 'Failed to update alert status.');
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
      <div className="alerts-header">
        <div>
          <h1 className="alerts-title">Security Alert Investigation Queue</h1>
          <p className="alerts-subtitle">
            Prioritized incidents generated from ML threat scoring, ANN reconstruction anomalies, and behavioral baselines.
          </p>
        </div>

        <div className="alerts-count-tag">
          <ShieldAlert size={14} />
          <span>{data?.total ?? 0} Recorded Incidents</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card alerts-filter-bar">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search by User ID, employee name, or incident reason..."
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              setPage(1);
            }}
          />
        </div>

        <div className="filter-controls">
          <select
            className="filter-select"
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
            className="filter-select"
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
        <LoadingSpinner message="Querying incident queue..." />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title={severity || status || searchInput ? 'No Matching Alerts' : 'No Security Alerts'}
          description={
            severity || status || searchInput
              ? 'No alerts match your filter parameters.'
              : 'No alerts have been generated. Alerts are automatically triggered when hybrid threat scores or anomaly reconstruction errors exceed calibrated thresholds.'
          }
          actionLabel={severity || status || searchInput ? 'Reset Filters' : 'View Models'}
          onAction={severity || status || searchInput ? clearFilters : () => navigate('/models')}
        />
      ) : (
        <div className="card alerts-table-card">
          <div className="table-responsive">
            <table className="alerts-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Incident ID</th>
                  <th>User ID</th>
                  <th>Employee</th>
                  <th>Reason</th>
                  <th>Risk Score</th>
                  <th>Detected At</th>
                  <th>Status</th>
                  <th>Action</th>
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
                    <td className="font-mono font-bold">{alert.user_id}</td>
                    <td>{alert.employee_name || '—'}</td>
                    <td className="reason-cell" title={alert.reason}>
                      {alert.reason}
                    </td>
                    <td className="font-mono">{formatRiskScore(alert.risk_score)}</td>
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
            <div className="pagination-footer">
              <span className="pagination-info text-muted">
                Page {data.page} of {data.total_pages} ({data.total} total alerts)
              </span>
              <div className="pagination-buttons">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={14} />
                  <span>Previous</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= data.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <span>Next</span>
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Alert Investigation & Triage Modal */}
      <Modal
        isOpen={Boolean(selectedAlert)}
        onClose={closeAlertModal}
        title={`Incident Dossier #${selectedAlert?.id}`}
        maxWidth={680}
      >
        {selectedAlert && (
          <div className="alert-modal-content">
            <div className="modal-incident-header">
              <div className="modal-header-badges">
                <span className={`badge ${getSeverityBadgeClass(selectedAlert.severity)}`}>
                  {selectedAlert.severity} Severity
                </span>
                <span className={`badge ${getStatusBadgeClass(selectedAlert.status)}`}>
                  Status: {selectedAlert.status}
                </span>
              </div>
              <span className="font-mono text-muted">Date: {formatDate(selectedAlert.date)}</span>
            </div>

            <h4 className="incident-reason">{selectedAlert.reason}</h4>

            {/* Entity Context */}
            <div className="modal-context-box">
              <div className="context-item">
                <span className="context-label">Target Entity:</span>
                <Link
                  to={`/users/${selectedAlert.user_id}`}
                  className="context-link font-mono"
                  onClick={closeAlertModal}
                >
                  <span>{selectedAlert.user_id}</span>
                  <ExternalLink size={12} />
                </Link>
              </div>
              <div className="context-item">
                <span className="context-label">Employee:</span>
                <span>{selectedAlert.employee_name || '—'}</span>
              </div>
              <div className="context-item">
                <span className="context-label">Department:</span>
                <span>{selectedAlert.department || '—'}</span>
              </div>
              <div className="context-item">
                <span className="context-label">Assessed Risk:</span>
                <span className="font-mono font-bold">
                  {formatRiskScore(selectedAlert.risk_score)}/100
                </span>
              </div>
            </div>

            {/* Evidence Payload */}
            {selectedAlert.evidence && (
              <div className="evidence-section">
                <h5 className="evidence-heading">Detection Evidence & Telemetry Signals</h5>
                <pre className="evidence-json-block font-mono">
                  {JSON.stringify(selectedAlert.evidence, null, 2)}
                </pre>
              </div>
            )}

            {/* Persistent Status Update Form */}
            <form onSubmit={handleUpdateStatus} className="status-update-form">
              <h5 className="evidence-heading">Analyst Triage & Status Update</h5>

              {updateSuccess && (
                <div className="status-feedback success-feedback">{updateSuccess}</div>
              )}
              {updateError && (
                <div className="status-feedback error-feedback">{updateError}</div>
              )}

              <div className="form-group">
                <label className="form-label">Investigation Status:</label>
                <select
                  className="form-select"
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                >
                  <option value="OPEN">OPEN — Awaiting Triage</option>
                  <option value="INVESTIGATING">INVESTIGATING — SOC Analyst Active</option>
                  <option value="RESOLVED">RESOLVED — Incident Closed</option>
                  <option value="DISMISSED">DISMISSED — Benign / False Positive</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Analyst Case Notes:</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="Record SOC rationale, employee interviews, or remediation actions..."
                  value={statusNotes}
                  onChange={(e) => setStatusNotes(e.target.value)}
                />
              </div>

              <div className="form-actions">
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
                  <Save size={14} />
                  <span>{isUpdating ? 'Persisting...' : 'Save & Persist Status'}</span>
                </button>
              </div>
            </form>
          </div>
        )}
      </Modal>
    </div>
  );
}
