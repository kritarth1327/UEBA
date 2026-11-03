import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Users,
  ShieldAlert,
  AlertTriangle,
  Activity,
  CheckCircle2,
  Clock,
  ArrowRight,
  Database,
  Cpu,
  Layers,
  FileSpreadsheet,
  ExternalLink,
  Shield,
  Sliders,
  FolderOpen,
  Terminal,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
  AreaChart,
  Area,
} from 'recharts';
import { useApi } from '../hooks/useApi';
import { api } from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import {
  formatDate,
  formatDateTime,
  formatRiskScore,
  getRiskBadgeClass,
  getSeverityBadgeClass,
  getStatusBadgeClass,
} from '../utils/formatters';
import './DashboardPage.css';

export function DashboardPage() {
  const navigate = useNavigate();
  const { data, loading, error, execute } = useApi(api.getDashboardOverview);

  if (loading) {
    return <LoadingSpinner message="Loading operational intelligence overview..." />;
  }

  if (error) {
    return <ErrorAlert message={error} onRetry={execute} />;
  }

  const hasData = data && data.total_users > 0;

  // Chart data formatting
  const riskChartData = data?.risk_distribution
    ? [
        { name: 'High (≥70)', count: data.risk_distribution.high, color: '#c2410c' },
        { name: 'Medium (40-69)', count: data.risk_distribution.medium, color: '#b45309' },
        { name: 'Low (<40)', count: data.risk_distribution.low, color: '#15803d' },
      ]
    : [];

  const totalAlerts = data?.alerts_by_severity
    ? data.alerts_by_severity.critical +
      data.alerts_by_severity.high +
      data.alerts_by_severity.medium +
      data.alerts_by_severity.low
    : 0;

  return (
    <div className="dashboard-page">
      {/* 1. Compact Operational Summary Strip */}
      <div className="operational-summary-strip">
        <div className="summary-strip-left">
          <div className="status-indicator-dot" />
          <div className="summary-mission-block">
            <span className="summary-mission-title">
              {hasData ? 'Active Telemetry Ingestion' : 'Pre-Ingestion Operational Mode'}
            </span>
            <span className="summary-mission-sub text-muted">
              {hasData
                ? `Monitoring ${data.total_users} enterprise identities & behavior profiles`
                : 'Awaiting CERT Insider Threat Dataset r4.2 archives in data/raw/r4.2/'}
            </span>
          </div>
        </div>

        <div className="summary-metrics-bar">
          <div className="metric-cell" onClick={() => navigate('/users')}>
            <span className="m-label">Entities</span>
            <span className="m-value font-mono">{data?.total_users ?? 0}</span>
          </div>
          <div className="metric-divider" />
          <div className="metric-cell" onClick={() => navigate('/alerts')}>
            <span className="m-label">Active Alerts</span>
            <span className="m-value font-mono">
              {totalAlerts}
              {data?.alerts_by_severity?.critical > 0 && (
                <span className="m-crit font-mono"> ({data.alerts_by_severity.critical} Crit)</span>
              )}
            </span>
          </div>
          <div className="metric-divider" />
          <div className="metric-cell" onClick={() => navigate('/users?sort_by=risk&sort_dir=desc')}>
            <span className="m-label">High Risk</span>
            <span className="m-value font-mono text-orange">{data?.risk_distribution?.high ?? 0}</span>
          </div>
          <div className="metric-divider" />
          <div className="metric-cell" onClick={() => navigate('/models')}>
            <span className="m-label">Engines</span>
            <span className="m-value font-mono text-teal">3 Active</span>
          </div>
        </div>
      </div>

      {/* 2. Asymmetric Analyst Workspace Grid */}
      <div className="analyst-workspace-grid">
        {/* Dominant Left Column (65% width) */}
        <div className="workspace-main-column">
          {/* Main Visualizer or Pre-Ingestion Ingestion Console */}
          {!hasData ? (
            <div className="card console-status-panel">
              <div className="console-panel-header">
                <div className="console-title-group">
                  <Database size={16} className="text-teal" />
                  <div>
                    <h3 className="console-title">CERT r4.2 Dataset Ingestion Pipeline</h3>
                    <span className="console-sub text-muted">
                      Pipeline foundation is initialized. Waiting for raw log extraction.
                    </span>
                  </div>
                </div>
                <Link to="/system" className="btn btn-secondary btn-sm">
                  <span>System Diagnostics</span>
                  <ArrowRight size={12} />
                </Link>
              </div>

              <div className="ingestion-checklist-grid">
                <div className="checklist-item">
                  <span className="chk-label">Raw Storage Path</span>
                  <span className="chk-val font-mono">data/raw/r4.2/</span>
                </div>
                <div className="checklist-item">
                  <span className="chk-label">Required Log Archives</span>
                  <span className="chk-val">logon.csv, device.csv, file.csv, email.csv, http.csv</span>
                </div>
                <div className="checklist-item">
                  <span className="chk-label">Aggregation Schema</span>
                  <span className="chk-val font-mono">DailyBehaviorProfile (User-Day)</span>
                </div>
                <div className="checklist-item">
                  <span className="chk-label">Detection Triad</span>
                  <span className="chk-val">XGBoost (45%) + Autoencoder (35%) + Baselines (20%)</span>
                </div>
              </div>

              <div className="console-terminal-note">
                <Terminal size={14} className="text-muted" />
                <span className="font-mono text-muted">
                  Pipeline trigger: Extract CERT r4.2 to data/raw/r4.2/ & execute user-day aggregation
                </span>
              </div>
            </div>
          ) : (
            <div className="card dominant-chart-panel">
              <div className="chart-header-row">
                <div>
                  <h3 className="section-title">Enterprise Activity Volume vs Baseline Deviations</h3>
                  <span className="section-subtitle text-muted">
                    Time series of observed enterprise logs against statistical threshold violations
                  </span>
                </div>
              </div>
              <div style={{ height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.activity_trends} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="totalEventsGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0e7490" stopOpacity={0.16}/>
                        <stop offset="95%" stopColor="#0e7490" stopOpacity={0.0}/>
                      </linearGradient>
                      <linearGradient id="anomEventsGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#c2410c" stopOpacity={0.22}/>
                        <stop offset="95%" stopColor="#c2410c" stopOpacity={0.0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#edf2f7" />
                    <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickFormatter={formatDate} />
                    <YAxis stroke="#94a3b8" fontSize={11} />
                    <Tooltip
                      contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: 12, boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}
                      labelStyle={{ color: '#0f172a', fontWeight: 600 }}
                    />
                    <Area type="monotone" dataKey="total_events" name="Total Activity Events" stroke="#0e7490" fill="url(#totalEventsGradient)" strokeWidth={2} />
                    <Area type="monotone" dataKey="anomalous_events" name="Anomalous Baseline Spikes" stroke="#c2410c" fill="url(#anomEventsGradient)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Prioritized Investigation Queue Table */}
          <div className="card workspace-table-panel">
            <div className="table-header-row">
              <div className="th-title-group">
                <h3 className="section-title">Prioritized Investigation Queue</h3>
                <span className="section-subtitle text-muted">
                  Entities sorted by calibrated multi-signal threat index
                </span>
              </div>
              <Link to="/users?sort_by=risk&sort_dir=desc" className="table-action-link">
                <span>View Full Directory</span>
                <ArrowRight size={13} />
              </Link>
            </div>

            {!hasData || data.highest_risk_users.length === 0 ? (
              <EmptyState
                icon={Users}
                title="Investigation Queue Clear"
                description="No high-risk entities detected. Entity risk assessments will be computed upon CERT r4.2 ingestion."
                actionLabel="Explore Entities"
                onAction={() => navigate('/users')}
                variant="inline"
              />
            ) : (
              <div className="table-responsive">
                <table className="compact-table">
                  <thead>
                    <tr>
                      <th>Entity Identifier</th>
                      <th>Department</th>
                      <th>Hybrid Threat Index</th>
                      <th>Risk Tier</th>
                      <th>Alerts</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.highest_risk_users.map((u) => (
                      <tr
                        key={u.user_id}
                        className="clickable-row"
                        onClick={() => navigate(`/users/${u.user_id}`)}
                      >
                        <td className="font-mono font-bold text-primary">{u.user_id}</td>
                        <td>{u.department || '—'}</td>
                        <td className="font-mono font-bold">
                          <div className="risk-score-pill font-mono">
                            {formatRiskScore(u.hybrid_risk_score)}
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${getRiskBadgeClass(u.risk_level)}`}>
                            {u.risk_level}
                          </span>
                        </td>
                        <td className="font-mono font-semibold">{u.alert_count}</td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/users/${u.user_id}`);
                            }}
                          >
                            Investigate
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Side Column (35% width) */}
        <div className="workspace-side-column">
          {/* Incident Triage Snapshot */}
          <div className="card side-panel">
            <div className="side-panel-header">
              <div>
                <h3 className="section-title">Active Incident Feed</h3>
                <span className="section-subtitle text-muted">Recent security alerts</span>
              </div>
              <Link to="/alerts" className="table-action-link">
                <span>Queue</span>
                <ArrowRight size={12} />
              </Link>
            </div>

            {!hasData || data.recent_alerts.length === 0 ? (
              <EmptyState
                icon={ShieldAlert}
                title="No Active Incidents"
                description="Alert triggers activate when hybrid risk exceeds 70 or when autoencoder reconstruction errors violate thresholds."
                variant="inline"
              />
            ) : (
              <div className="recent-alerts-list">
                {data.recent_alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="alert-feed-item"
                    onClick={() => navigate('/alerts')}
                  >
                    <div className="feed-item-top">
                      <span className={`badge ${getSeverityBadgeClass(alert.severity)}`}>
                        {alert.severity}
                      </span>
                      <span className="font-mono feed-user">{alert.user_id}</span>
                      <span className="feed-status text-muted">{alert.status}</span>
                    </div>
                    <p className="feed-reason" title={alert.reason}>
                      {alert.reason}
                    </p>
                    <span className="feed-date text-muted font-mono">
                      {formatDateTime(alert.detected_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Population Risk Spectrum */}
          <div className="card side-panel">
            <h3 className="section-title">Population Risk Stratification</h3>
            <span className="section-subtitle text-muted">
              Entities categorized by calibrated threat boundaries
            </span>

            <div className="risk-spectrum-list">
              <div
                className="spectrum-row"
                onClick={() => navigate('/users?sort_by=risk&sort_dir=desc')}
              >
                <div className="spec-info">
                  <span className="spec-dot dot-high" />
                  <span className="spec-name">High Risk (&ge; 70)</span>
                </div>
                <span className="font-mono font-bold text-orange">
                  {data?.risk_distribution?.high ?? 0}
                </span>
              </div>

              <div
                className="spectrum-row"
                onClick={() => navigate('/users?sort_by=risk&sort_dir=desc')}
              >
                <div className="spec-info">
                  <span className="spec-dot dot-med" />
                  <span className="spec-name">Medium Risk (40-69)</span>
                </div>
                <span className="font-mono font-bold text-amber">
                  {data?.risk_distribution?.medium ?? 0}
                </span>
              </div>

              <div
                className="spectrum-row"
                onClick={() => navigate('/users')}
              >
                <div className="spec-info">
                  <span className="spec-dot dot-low" />
                  <span className="spec-name">Low Risk (&lt; 40)</span>
                </div>
                <span className="font-mono font-bold text-low">
                  {data?.risk_distribution?.low ?? 0}
                </span>
              </div>

              <div className="spectrum-row">
                <div className="spec-info">
                  <span className="spec-dot dot-unassessed" />
                  <span className="spec-name">Unassessed</span>
                </div>
                <span className="font-mono text-muted">
                  {data?.risk_distribution?.unassessed ?? 0}
                </span>
              </div>
            </div>
          </div>

          {/* Detection Triad Engine Blueprint */}
          <div className="card side-panel blueprint-panel">
            <h3 className="section-title">Detection Signal Weights</h3>
            <span className="section-subtitle text-muted">
              Calibrated multi-signal weighted fusion model
            </span>

            <div className="blueprint-weights">
              <div className="weight-bar-item">
                <div className="w-label-row">
                  <span className="w-title">Supervised Threat (XGBoost)</span>
                  <span className="w-pct font-mono">45%</span>
                </div>
                <div className="w-track">
                  <div className="w-fill fill-teal" style={{ width: '45%' }} />
                </div>
              </div>

              <div className="weight-bar-item">
                <div className="w-label-row">
                  <span className="w-title">Neural Autoencoder (MSE)</span>
                  <span className="w-pct font-mono">35%</span>
                </div>
                <div className="w-track">
                  <div className="w-fill fill-purple" style={{ width: '35%' }} />
                </div>
              </div>

              <div className="weight-bar-item">
                <div className="w-label-row">
                  <span className="w-title">Personal Baseline (&sigma;)</span>
                  <span className="w-pct font-mono">20%</span>
                </div>
                <div className="w-track">
                  <div className="w-fill fill-amber" style={{ width: '20%' }} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
