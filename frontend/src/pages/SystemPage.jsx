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
  Code2,
  ArrowRight,
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
      setError(err.message || 'Failed to query system diagnostics.');
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
      return <CheckCircle2 size={17} className="status-ico text-low" />;
    }
    if (s === 'partial' || s === 'pending' || s === 'processed' || s === 'pending_data') {
      return <AlertTriangle size={17} className="status-ico text-medium" />;
    }
    return <XCircle size={17} className="status-ico text-critical" />;
  };

  const getStatusBadge = (status) => {
    const s = (status || '').toLowerCase();
    if (s === 'healthy' || s === 'ready' || s === 'connected' || s === 'operational') {
      return <span className="badge badge-low">{status}</span>;
    }
    if (s === 'partial' || s === 'pending' || s === 'processed' || s === 'pending_data') {
      return <span className="badge badge-medium">{status}</span>;
    }
    return <span className="badge badge-critical">{status || 'Unavailable'}</span>;
  };

  if (loading) {
    return <LoadingSpinner message="Auditing infrastructure and dataset diagnostics..." />;
  }

  return (
    <div className="system-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">System Infrastructure & Dataset Diagnostics</h1>
          <p className="page-subtitle">
            Operational status of FastAPI backend, database persistence, CERT r4.2 raw log files, and detection pipeline.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary btn-sm refresh-btn"
          onClick={() => fetchStatus(true)}
          disabled={refreshing}
        >
          <RefreshCw size={13} className={refreshing ? 'spinner-icon' : ''} />
          <span>{refreshing ? 'Auditing...' : 'Run Diagnostics'}</span>
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
                <h3 className="overall-heading">
                  System Readiness:{' '}
                  <span className="font-mono">{systemData.overall_status.toUpperCase()}</span>
                </h3>
                <p className="overall-timestamp text-muted">
                  Diagnostic timestamp: {formatDateTime(systemData.timestamp)}
                </p>
              </div>
            </div>
            {getStatusBadge(systemData.overall_status)}
          </div>

          {/* Component Diagnostics Grid */}
          <div className="components-grid">
            {/* 1. FastAPI Application */}
            <div className="card component-card">
              <div className="component-top">
                <div className="comp-title-group">
                  <Server size={17} className="text-teal" />
                  <span className="comp-name">FastAPI Backend</span>
                </div>
                {getStatusBadge(systemData.backend_status?.status)}
              </div>
              <p className="comp-desc text-muted">{systemData.backend_status?.message}</p>
              <div className="comp-specs">
                <div className="spec-row">
                  <span className="spec-key">Python Environment:</span>
                  <span className="spec-val font-mono">
                    {systemData.backend_status?.details?.python_version || '3.14.7'}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">API Version:</span>
                  <span className="spec-val font-mono">v1</span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Architecture:</span>
                  <span className="spec-val">RESTful Microservice</span>
                </div>
              </div>
            </div>

            {/* 2. Database Connection */}
            <div className="card component-card">
              <div className="component-top">
                <div className="comp-title-group">
                  <Database size={17} className="text-teal" />
                  <span className="comp-name">Database Persistence</span>
                </div>
                {getStatusBadge(systemData.database_status?.status)}
              </div>
              <p className="comp-desc text-muted">{systemData.database_status?.message}</p>
              <div className="comp-specs">
                <div className="spec-row">
                  <span className="spec-key">Dialect / Driver:</span>
                  <span className="spec-val font-mono">
                    {systemData.database_status?.details?.driver || 'sqlite'}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Persisted Entities:</span>
                  <span className="spec-val font-mono">
                    {systemData.database_status?.details?.persisted_users ?? 0}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Behavior Profiles:</span>
                  <span className="spec-val font-mono">
                    {systemData.database_status?.details?.persisted_profiles ?? 0}
                  </span>
                </div>
              </div>
            </div>

            {/* 3. CERT r4.2 Raw Logs */}
            <div className="card component-card">
              <div className="component-top">
                <div className="comp-title-group">
                  <FileSpreadsheet size={17} className="text-amber" />
                  <span className="comp-name">CERT r4.2 Raw Logs</span>
                </div>
                {getStatusBadge(systemData.dataset_status?.status)}
              </div>
              <p className="comp-desc text-muted">{systemData.dataset_status?.message}</p>
              <div className="comp-specs">
                <div className="spec-row">
                  <span className="spec-key">Target Path:</span>
                  <span className="spec-val font-mono path-text">data/raw/r4.2/</span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Core Files Found:</span>
                  <span className="spec-val font-mono">
                    {systemData.dataset_status?.details?.files_found?.length || 0} /{' '}
                    {systemData.dataset_status?.details?.expected_files?.length || 5}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Required:</span>
                  <span className="spec-val text-muted">logon, device, file, email, http</span>
                </div>
              </div>
            </div>

            {/* 4. Processing Pipeline */}
            <div className="card component-card">
              <div className="component-top">
                <div className="comp-title-group">
                  <Workflow size={17} className="text-teal" />
                  <span className="comp-name">Behavioral Aggregation</span>
                </div>
                {getStatusBadge(systemData.pipeline_status?.status)}
              </div>
              <p className="comp-desc text-muted">{systemData.pipeline_status?.message}</p>
              <div className="comp-specs">
                <div className="spec-row">
                  <span className="spec-key">Aggregation Unit:</span>
                  <span className="spec-val">User-Day Behavioral Record</span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Baselines:</span>
                  <span className="spec-val">Longitudinal Moving Statistics</span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Leakage Control:</span>
                  <span className="spec-val font-mono">Strict Train/Test Split</span>
                </div>
              </div>
            </div>

            {/* 5. Detection Models */}
            <div className="card component-card">
              <div className="component-top">
                <div className="comp-title-group">
                  <Cpu size={17} className="text-purple" />
                  <span className="comp-name">Inference Model Weights</span>
                </div>
                {getStatusBadge(systemData.model_status?.status)}
              </div>
              <p className="comp-desc text-muted">{systemData.model_status?.message}</p>
              <div className="comp-specs">
                <div className="spec-row">
                  <span className="spec-key">XGBoost Classifier:</span>
                  <span className="spec-val">
                    {systemData.model_status?.details?.xgboost_available ? 'Loaded' : 'Pending Weights'}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Dense Autoencoder:</span>
                  <span className="spec-val">
                    {systemData.model_status?.details?.autoencoder_available ? 'Loaded' : 'Pending Weights'}
                  </span>
                </div>
                <div className="spec-row">
                  <span className="spec-key">Artifacts Path:</span>
                  <span className="spec-val font-mono path-text">backend/artifacts/</span>
                </div>
              </div>
            </div>
          </div>

          {/* Actionable Pipeline Guide */}
          <div className="card guide-card">
            <h3 className="section-title">CERT r4.2 Data Pipeline Integration Protocol</h3>
            <p className="section-subtitle text-muted">
              Execution steps once the CERT Insider Threat Dataset r4.2 download finishes:
            </p>

            <div className="protocol-steps">
              <div className="protocol-step">
                <div className="step-circle font-mono">1</div>
                <div className="step-detail">
                  <h4 className="step-title">Extract Raw Logs to Target Folder</h4>
                  <p className="step-text text-muted">
                    Extract CERT r4.2 CSV archives directly into <code className="code-chip">data/raw/r4.2/</code>. Verify that <code className="code-chip">logon.csv</code>, <code className="code-chip">file.csv</code>, <code className="code-chip">device.csv</code>, <code className="code-chip">email.csv</code>, and <code className="code-chip">http.csv</code> exist.
                  </p>
                </div>
              </div>

              <div className="protocol-step">
                <div className="step-circle font-mono">2</div>
                <div className="step-detail">
                  <h4 className="step-title">Execute Preprocessing & User-Day Feature Aggregation</h4>
                  <p className="step-text text-muted">
                    Runs timestamp parsing, user mapping, session calculation, off-hours event filtering, and multi-source combinations. Persists aggregated profiles into <code className="code-chip">data/processed/</code> and the backend database.
                  </p>
                </div>
              </div>

              <div className="protocol-step">
                <div className="step-circle font-mono">3</div>
                <div className="step-detail">
                  <h4 className="step-title">Train Supervised ML & Neural Autoencoder</h4>
                  <p className="step-text text-muted">
                    Fits XGBoost on labeled threat scenarios, trains the Dense Autoencoder on benign activity to establish reconstruction error thresholds, and computes personal baselines. Model artifacts are saved to <code className="code-chip">backend/artifacts/</code>.
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
