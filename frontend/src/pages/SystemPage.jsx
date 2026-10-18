import React, { useState, useEffect } from 'react';
import {
  Server,
  Database,
  FileSpreadsheet,
  Workflow,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  RefreshCw,
  FolderOpen,
  Terminal,
} from 'lucide-react';
import { api } from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { formatDateTime } from '../utils/formatters';
import './SystemPage.css';

export function SystemPage() {
  const [systemData, setSystemData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const res = await api.getSystemStatus();
      setSystemData(res);
    } catch (err) {
      setError(err.message || 'Failed to query system status diagnostics.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const getStatusIcon = (status) => {
    const s = (status || '').toLowerCase();
    if (s === 'healthy' || s === 'ready' || s === 'connected' || s === 'operational') {
      return <CheckCircle2 size={18} className="status-icon text-low" />;
    }
    if (s === 'partial' || s === 'pending' || s === 'processed') {
      return <AlertTriangle size={18} className="status-icon text-medium" />;
    }
    return <XCircle size={18} className="status-icon text-critical" />;
  };

  const getStatusBadge = (status) => {
    const s = (status || '').toLowerCase();
    if (s === 'healthy' || s === 'ready' || s === 'connected' || s === 'operational') {
      return <span className="badge badge-low">{status}</span>;
    }
    if (s === 'partial' || s === 'pending' || s === 'processed') {
      return <span className="badge badge-medium">{status}</span>;
    }
    return <span className="badge badge-critical">{status || 'Unavailable'}</span>;
  };

  if (loading) {
    return <LoadingSpinner message="Evaluating operational diagnostics..." />;
  }

  return (
    <div className="system-page">
      <div className="system-header">
        <div>
          <h1 className="system-title">System Infrastructure & Dataset Readiness</h1>
          <p className="system-subtitle">
            Diagnostics for backend API, database persistence, CERT r4.2 raw log files, and detection pipeline.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary btn-sm refresh-btn"
          onClick={() => fetchStatus(true)}
          disabled={refreshing}
        >
          <RefreshCw size={14} className={refreshing ? 'spinner-icon' : ''} />
          <span>{refreshing ? 'Refreshing...' : 'Run Diagnostics'}</span>
        </button>
      </div>

      {error && <ErrorAlert message={error} onRetry={() => fetchStatus(false)} />}

      {systemData && (
        <>
          {/* Overall Status Banner */}
          <div className="card overall-status-card">
            <div className="overall-left">
              {getStatusIcon(systemData.overall_status)}
              <div>
                <h3 className="overall-title">
                  System Status:{' '}
                  <span className="font-mono">{systemData.overall_status.toUpperCase()}</span>
                </h3>
                <p className="overall-desc text-muted">
                  Last checked: {formatDateTime(systemData.timestamp)}
                </p>
              </div>
            </div>
            {getStatusBadge(systemData.overall_status)}
          </div>

          {/* Component Diagnostics Grid */}
          <div className="components-grid">
            {/* 1. Backend Server */}
            <div className="card component-card">
              <div className="component-header">
                <div className="component-title-box">
                  <Server size={18} className="component-icon text-teal" />
                  <span className="component-name">FastAPI Application</span>
                </div>
                {getStatusBadge(systemData.backend_status?.status)}
              </div>
              <p className="component-msg">{systemData.backend_status?.message}</p>
              <div className="component-details-box">
                <div className="detail-row">
                  <span className="d-label">Python Environment:</span>
                  <span className="d-val font-mono">
                    {systemData.backend_status?.details?.python_version || '3.14.7'}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="d-label">API Version:</span>
                  <span className="d-val font-mono">v1</span>
                </div>
              </div>
            </div>

            {/* 2. Database Connection */}
            <div className="card component-card">
              <div className="component-header">
                <div className="component-title-box">
                  <Database size={18} className="component-icon text-teal" />
                  <span className="component-name">Database Persistence</span>
                </div>
                {getStatusBadge(systemData.database_status?.status)}
              </div>
              <p className="component-msg">{systemData.database_status?.message}</p>
              <div className="component-details-box">
                <div className="detail-row">
                  <span className="d-label">Dialect / Driver:</span>
                  <span className="d-val font-mono">
                    {systemData.database_status?.details?.driver || 'sqlite'}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="d-label">Persisted Users:</span>
                  <span className="d-val font-mono">
                    {systemData.database_status?.details?.persisted_users ?? 0}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="d-label">Behavior Records:</span>
                  <span className="d-val font-mono">
                    {systemData.database_status?.details?.persisted_profiles ?? 0}
                  </span>
                </div>
              </div>
            </div>

            {/* 3. CERT Dataset Availability */}
            <div className="card component-card">
              <div className="component-header">
                <div className="component-title-box">
                  <FileSpreadsheet size={18} className="component-icon text-amber" />
                  <span className="component-name">CERT r4.2 Raw Logs</span>
                </div>
                {getStatusBadge(systemData.dataset_status?.status)}
              </div>
              <p className="component-msg">{systemData.dataset_status?.message}</p>
              <div className="component-details-box">
                <div className="detail-row">
                  <span className="d-label">Target Directory:</span>
                  <span className="d-val font-mono path-text">
                    data/raw/r4.2/
                  </span>
                </div>
                <div className="detail-row">
                  <span className="d-label">Core Files Found:</span>
                  <span className="d-val font-mono">
                    {systemData.dataset_status?.details?.files_found?.length || 0} /{' '}
                    {systemData.dataset_status?.details?.expected_files?.length || 5}
                  </span>
                </div>
              </div>
            </div>

            {/* 4. Processing Pipeline */}
            <div className="card component-card">
              <div className="component-header">
                <div className="component-title-box">
                  <Workflow size={18} className="component-icon text-teal" />
                  <span className="component-name">Behavioral Aggregation Pipeline</span>
                </div>
                {getStatusBadge(systemData.pipeline_status?.status)}
              </div>
              <p className="component-msg">{systemData.pipeline_status?.message}</p>
              <div className="component-details-box">
                <div className="detail-row">
                  <span className="d-label">Unit of Analysis:</span>
                  <span className="d-val">User-Day Behavioral Record</span>
                </div>
                <div className="detail-row">
                  <span className="d-label">Baseline Type:</span>
                  <span className="d-val">Personal Longitudinal Normal</span>
                </div>
              </div>
            </div>

            {/* 5. Detection Models */}
            <div className="card component-card">
              <div className="component-header">
                <div className="component-title-box">
                  <Cpu size={18} className="component-icon text-purple" />
                  <span className="component-name">ML & ANN Inference Artifacts</span>
                </div>
                {getStatusBadge(systemData.model_status?.status)}
              </div>
              <p className="component-msg">{systemData.model_status?.message}</p>
              <div className="component-details-box">
                <div className="detail-row">
                  <span className="d-label">XGBoost Classifier:</span>
                  <span className="d-val">
                    {systemData.model_status?.details?.xgboost_available ? 'Ready' : 'Pending Weights'}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="d-label">Autoencoder:</span>
                  <span className="d-val">
                    {systemData.model_status?.details?.autoencoder_available ? 'Ready' : 'Pending Weights'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Actionable Pipeline Guide */}
          <div className="card pipeline-guide-card">
            <h3 className="section-title">CERT r4.2 Ingestion & Training Instructions</h3>
            <p className="section-subtitle text-muted">
              Follow these commands when the CERT Insider Threat Dataset r4.2 download completes:
            </p>

            <div className="guide-steps">
              <div className="guide-step">
                <span className="step-num font-mono">1</span>
                <div className="step-content">
                  <h4 className="step-heading">Extract Raw Logs to Target Directory</h4>
                  <p className="step-desc">
                    Extract the CERT archive directly into <code className="font-mono">data/raw/r4.2/</code>. Ensure <code className="font-mono">logon.csv</code>, <code className="font-mono">file.csv</code>, <code className="font-mono">device.csv</code>, <code className="font-mono">email.csv</code>, and <code className="font-mono">http.csv</code> are present.
                  </p>
                </div>
              </div>

              <div className="guide-step">
                <span className="step-num font-mono">2</span>
                <div className="step-content">
                  <h4 className="step-heading">Execute Feature Engineering & Aggregation</h4>
                  <p className="step-desc">
                    Aggregates daily events per user into user-day feature profiles and stores them in <code className="font-mono">data/processed/</code>.
                  </p>
                </div>
              </div>

              <div className="guide-step">
                <span className="step-num font-mono">3</span>
                <div className="step-content">
                  <h4 className="step-heading">Train Detection Models</h4>
                  <p className="step-desc">
                    Trains the supervised XGBoost threat classifier on threat scenarios, fits the Dense Autoencoder on normal profiles, and establishes personal baselines. Model checkpoints are automatically written to <code className="font-mono">backend/artifacts/</code>.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
