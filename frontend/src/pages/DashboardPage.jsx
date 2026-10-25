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
  TrendingUp,
  FileSpreadsheet,
  ExternalLink,
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
    return <LoadingSpinner message="Querying enterprise security telemetry..." />;
  }

  if (error) {
    return <ErrorAlert message={error} onRetry={execute} />;
  }

  const hasData = data && data.total_users > 0;

  // Chart data formatting
  const riskChartData = data?.risk_distribution
    ? [
        { name: 'High', count: data.risk_distribution.high, color: '#c2410c' },
        { name: 'Medium', count: data.risk_distribution.medium, color: '#b45309' },
        { name: 'Low', count: data.risk_distribution.low, color: '#15803d' },
      ]
    : [];

  const severityData = data?.alerts_by_severity
    ? [
        { name: 'Critical', count: data.alerts_by_severity.critical, color: '#991b1b' },
        { name: 'High', count: data.alerts_by_severity.high, color: '#c2410c' },
        { name: 'Medium', count: data.alerts_by_severity.medium, color: '#b45309' },
        { name: 'Low', count: data.alerts_by_severity.low, color: '#15803d' },
      ]
    : [];

  return (
    <div className="dashboard-page">
      {/* Header Banner */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Security Operations Overview</h1>
          <p className="page-subtitle">
            Enterprise entity behavior analytics, behavioral deviation scoring, and prioritized insider threat telemetry.
          </p>
        </div>

        <div className="dashboard-readiness-group">
          <div
            className={`readiness-pill ${
              data?.dataset_ready ? 'pill-ready' : 'pill-pending'
            }`}
          >
            <Database size={13} />
            <span>Dataset: {data?.dataset_ready ? 'Ingested' : 'Ingestion pending'}</span>
          </div>

          <div
            className={`readiness-pill ${
              data?.models_ready ? 'pill-ready' : 'pill-pending'
            }`}
          >
            <Cpu size={13} />
            <span>
              Inference:{' '}
              {data?.model_status === 'ready'
                ? 'All components online'
                : data?.model_status === 'partial'
                ? 'Partial scoring online'
                : 'Unavailable'}
            </span>
          </div>
        </div>
      </div>

      {/* KPI Metric Grid */}
      <div className="kpi-grid">
        <div className="card kpi-card" onClick={() => navigate('/users')}>
          <div className="kpi-top">
            <span className="kpi-label">Ingested Entities</span>
            <div className="kpi-icon-box">
              <Users size={16} className="text-teal" />
            </div>
          </div>
          <div className="kpi-value font-mono">{data?.total_users ?? 0}</div>
          <div className="kpi-subtext text-muted">
            <span className="font-mono text-primary font-medium">{data?.assessed_users ?? 0}</span> evaluated by detection pipeline
          </div>
        </div>

        <div className="card kpi-card" onClick={() => navigate('/alerts')}>
          <div className="kpi-top">
            <span className="kpi-label">Security Alerts</span>
            <div className="kpi-icon-box">
              <ShieldAlert size={16} className="text-amber" />
            </div>
          </div>
          <div className="kpi-value font-mono">
            {data?.alerts_by_severity
              ? data.alerts_by_severity.critical +
                data.alerts_by_severity.high +
                data.alerts_by_severity.medium +
                data.alerts_by_severity.low
              : 0}
          </div>
          <div className="kpi-subtext">
            <span className="font-mono font-bold text-critical">
              {data?.alerts_by_severity?.critical ?? 0} Critical
            </span>
            <span className="text-muted"> incidents requiring review</span>
          </div>
        </div>

        <div className="card kpi-card" onClick={() => navigate('/users?sort_by=risk&sort_dir=desc')}>
          <div className="kpi-top">
            <span className="kpi-label">Elevated Threat Profiles</span>
            <div className="kpi-icon-box">
              <AlertTriangle size={16} className="text-orange" />
            </div>
          </div>
          <div className="kpi-value font-mono">{data?.risk_distribution?.high ?? 0}</div>
          <div className="kpi-subtext text-muted">
            Hybrid risk score &ge; 70 calibrated threshold
          </div>
        </div>

        <div className="card kpi-card" onClick={() => navigate('/models')}>
          <div className="kpi-top">
            <span className="kpi-label">Detection Engines</span>
            <div className="kpi-icon-box">
              <Layers size={16} className="text-teal" />
            </div>
          </div>
          <div className="kpi-value font-mono">4 Components</div>
          <div className="kpi-subtext text-muted">
            General ML + CERT + ANN + Baseline
          </div>
        </div>
      </div>

      {!hasData ? (
        <EmptyState
          icon={FileSpreadsheet}
          title="Behavioral Dataset Ingestion Pending"
          description="No user-day behavioral profiles are currently persisted. Ingest one of the supported datasets, then run baseline generation and scoring to populate telemetry."
          actionLabel="View System & Dataset Diagnostics"
          onAction={() => navigate('/system')}
        />
      ) : (
        <>
          {/* Charts Row */}
          <div className="dashboard-charts-row">
            {/* Risk Distribution Chart */}
            <div className="card chart-panel">
              <div className="chart-panel-header">
                <div>
                  <h3 className="section-title">Risk Distribution</h3>
                  <span className="section-subtitle text-muted">User population categorization</span>
                </div>
              </div>
              <div className="chart-body" style={{ height: 190 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={riskChartData} layout="vertical" margin={{ top: 8, right: 24, left: 16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#edf2f7" horizontal={false} />
                    <XAxis type="number" stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                    <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={12} width={55} />
                    <Tooltip
                      contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: 12, boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}
                      labelStyle={{ color: '#0f172a', fontWeight: 600 }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={18}>
                      {riskChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Severity Breakdown */}
            <div className="card chart-panel">
              <div className="chart-panel-header">
                <div>
                  <h3 className="section-title">Alerts by Severity</h3>
                  <span className="section-subtitle text-muted">Incidents classified by severity</span>
                </div>
              </div>
              <div className="chart-body" style={{ height: 190 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={severityData} margin={{ top: 8, right: 16, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#edf2f7" vertical={false} />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: 12, boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}
                      labelStyle={{ color: '#0f172a', fontWeight: 600 }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={28}>
                      {severityData.map((entry, index) => (
                        <Cell key={`sev-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Activity Trends */}
          {data.activity_trends && data.activity_trends.length > 0 && (
            <div className="card chart-panel">
              <div className="chart-panel-header">
                <div>
                  <h3 className="section-title">Enterprise Activity Trends & Flagged Anomalies</h3>
                  <span className="section-subtitle text-muted">Timeline of observed enterprise events vs baseline deviations</span>
                </div>
              </div>
              <div style={{ height: 210 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.activity_trends} margin={{ top: 8, right: 24, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="totalEventsGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0891b2" stopOpacity={0.15}/>
                        <stop offset="95%" stopColor="#0891b2" stopOpacity={0.0}/>
                      </linearGradient>
                      <linearGradient id="anomEventsGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#c2410c" stopOpacity={0.2}/>
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
                    <Area type="monotone" dataKey="anomalous_events" name="Anomalous Signals" stroke="#c2410c" fill="url(#anomEventsGradient)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Tables Row */}
          <div className="dashboard-tables-row">
            {/* Top Risk Entities */}
            <div className="card dashboard-table-card">
              <div className="table-header-row">
                <div>
                  <h3 className="section-title">Highest Risk Entities</h3>
                  <span className="section-subtitle text-muted">Ranked by latest multi-signal hybrid score</span>
                </div>
                <Link to="/users?sort_by=risk&sort_dir=desc" className="view-link">
                  <span>View All Users</span>
                  <ArrowRight size={13} />
                </Link>
              </div>

              {data.highest_risk_users.length === 0 ? (
                <div className="table-empty-notice text-muted">No high-risk users identified.</div>
              ) : (
                <div className="table-responsive">
                  <table className="compact-table">
                    <thead>
                      <tr>
                        <th>Entity ID</th>
                        <th>Department</th>
                        <th>Hybrid Score</th>
                        <th>Classification</th>
                        <th>Alerts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.highest_risk_users.map((u) => (
                        <tr
                          key={u.user_id}
                          className="clickable-row"
                          onClick={() => navigate(`/users/${u.user_id}`)}
                        >
                          <td className="font-mono font-semibold text-primary">{u.user_id}</td>
                          <td>{u.department || '—'}</td>
                          <td className="font-mono font-medium">{formatRiskScore(u.hybrid_risk_score)}</td>
                          <td>
                            <span className={`badge ${getRiskBadgeClass(u.risk_level)}`}>
                              {u.risk_level}
                            </span>
                          </td>
                          <td className="font-mono">{u.alert_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Recent Alerts Feed */}
            <div className="card dashboard-table-card">
              <div className="table-header-row">
                <div>
                  <h3 className="section-title">Recent Alert Queue</h3>
                  <span className="section-subtitle text-muted">Latest triggered security incidents</span>
                </div>
                <Link to="/alerts" className="view-link">
                  <span>View Queue</span>
                  <ArrowRight size={13} />
                </Link>
              </div>

              {data.recent_alerts.length === 0 ? (
                <div className="table-empty-notice text-muted">No active alerts recorded.</div>
              ) : (
                <div className="table-responsive">
                  <table className="compact-table">
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>Entity</th>
                        <th>Reason</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_alerts.map((a) => (
                        <tr
                          key={a.id}
                          className="clickable-row"
                          onClick={() => navigate('/alerts')}
                        >
                          <td>
                            <span className={`badge ${getSeverityBadgeClass(a.severity)}`}>
                              {a.severity}
                            </span>
                          </td>
                          <td className="font-mono font-semibold text-primary">{a.user_id}</td>
                          <td className="cell-reason" title={a.reason}>
                            {a.reason}
                          </td>
                          <td>
                            <span className={`badge ${getStatusBadgeClass(a.status)}`}>
                              {a.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
