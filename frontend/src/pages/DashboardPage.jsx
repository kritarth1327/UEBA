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
} from 'recharts';
import { useApi } from '../hooks/useApi';
import { api } from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import {
  formatDate,
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
    return <LoadingSpinner message="Calculating security telemetry..." />;
  }

  if (error) {
    return <ErrorAlert message={error} onRetry={execute} />;
  }

  const hasData = data && data.total_users > 0;

  // Chart data formatting
  const riskChartData = data?.risk_distribution
    ? [
        { name: 'High', count: data.risk_distribution.high, color: '#e2753a' },
        { name: 'Medium', count: data.risk_distribution.medium, color: '#d99a26' },
        { name: 'Low', count: data.risk_distribution.low, color: '#36a36f' },
      ]
    : [];

  const severityData = data?.alerts_by_severity
    ? [
        { name: 'Critical', count: data.alerts_by_severity.critical, color: '#e04b4b' },
        { name: 'High', count: data.alerts_by_severity.high, color: '#e2753a' },
        { name: 'Medium', count: data.alerts_by_severity.medium, color: '#d99a26' },
        { name: 'Low', count: data.alerts_by_severity.low, color: '#36a36f' },
      ]
    : [];

  return (
    <div className="dashboard-page">
      {/* Page Title & Readiness Banner */}
      <div className="dashboard-header">
        <div>
          <h1 className="dashboard-title">Security Operations Overview</h1>
          <p className="dashboard-subtitle">
            Enterprise behavioral risk evaluation and threat telemetry.
          </p>
        </div>

        <div className="readiness-pills">
          <div
            className={`readiness-pill ${
              data?.dataset_ready ? 'pill-ready' : 'pill-pending'
            }`}
          >
            <Database size={13} />
            <span>Dataset: {data?.dataset_ready ? 'Ingested' : 'Pending r4.2'}</span>
          </div>

          <div
            className={`readiness-pill ${
              data?.models_ready ? 'pill-ready' : 'pill-pending'
            }`}
          >
            <Cpu size={13} />
            <span>Models: {data?.models_ready ? 'Ready' : 'Awaiting Training'}</span>
          </div>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div className="metrics-grid">
        <div className="card metric-card" onClick={() => navigate('/users')}>
          <div className="metric-header">
            <span className="metric-label">Total Ingested Users</span>
            <Users size={16} className="metric-icon" />
          </div>
          <div className="metric-value">{data?.total_users ?? 0}</div>
          <div className="metric-footer text-muted">
            {data?.assessed_users ?? 0} assessed by hybrid pipeline
          </div>
        </div>

        <div className="card metric-card" onClick={() => navigate('/alerts')}>
          <div className="metric-header">
            <span className="metric-label">Active Alerts</span>
            <ShieldAlert size={16} className="metric-icon" />
          </div>
          <div className="metric-value">
            {data?.alerts_by_severity
              ? data.alerts_by_severity.critical +
                data.alerts_by_severity.high +
                data.alerts_by_severity.medium +
                data.alerts_by_severity.low
              : 0}
          </div>
          <div className="metric-footer">
            <span className="metric-crit-count font-mono">
              {data?.alerts_by_severity?.critical ?? 0} Critical
            </span>
            <span className="text-muted"> requiring review</span>
          </div>
        </div>

        <div className="card metric-card" onClick={() => navigate('/users?sort_by=risk&sort_dir=desc')}>
          <div className="metric-header">
            <span className="metric-label">High Risk Profiles</span>
            <AlertTriangle size={16} className="metric-icon metric-icon-warn" />
          </div>
          <div className="metric-value">{data?.risk_distribution?.high ?? 0}</div>
          <div className="metric-footer text-muted">
            Hybrid score &ge; 70 threshold
          </div>
        </div>

        <div className="card metric-card" onClick={() => navigate('/models')}>
          <div className="metric-header">
            <span className="metric-label">Detection Engines</span>
            <Activity size={16} className="metric-icon" />
          </div>
          <div className="metric-value font-mono">3 Signals</div>
          <div className="metric-footer text-muted">
            XGBoost + Autoencoder + Baselines
          </div>
        </div>
      </div>

      {!hasData ? (
        <EmptyState
          icon={Database}
          title="CERT r4.2 Dataset Ingestion Pending"
          description="No employee behavior profiles have been ingested into the database yet. Place the CERT r4.2 log files in data/raw/r4.2/ and execute the processing pipeline to populate telemetry."
          actionLabel="Check System Status"
          onAction={() => navigate('/system')}
        />
      ) : (
        <>
          {/* Charts Row */}
          <div className="dashboard-charts-grid">
            {/* Risk Distribution Chart */}
            <div className="card chart-card">
              <div className="chart-header">
                <h3 className="chart-title">Risk Distribution</h3>
                <span className="chart-subtitle text-muted">Latest User Assessments</span>
              </div>
              <div className="chart-body" style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={riskChartData} layout="vertical" margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
                    <XAxis type="number" stroke="#677b95" fontSize={11} />
                    <YAxis dataKey="name" type="category" stroke="#9cb0c9" fontSize={12} width={60} />
                    <Tooltip
                      contentStyle={{ background: '#1c2430', border: '1px solid #37475e', borderRadius: 4 }}
                      labelStyle={{ color: '#e6edf5' }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {riskChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Severity Breakdown */}
            <div className="card chart-card">
              <div className="chart-header">
                <h3 className="chart-title">Alerts by Severity</h3>
                <span className="chart-subtitle text-muted">Security Incidents</span>
              </div>
              <div className="chart-body" style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={severityData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#263345" vertical={false} />
                    <XAxis dataKey="name" stroke="#9cb0c9" fontSize={12} />
                    <YAxis stroke="#677b95" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: '#1c2430', border: '1px solid #37475e', borderRadius: 4 }}
                      labelStyle={{ color: '#e6edf5' }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
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
            <div className="card trend-card">
              <div className="chart-header">
                <h3 className="chart-title">Daily Activity Volume & Anomaly Signals</h3>
                <span className="chart-subtitle text-muted">Aggregated events over observation period</span>
              </div>
              <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.activity_trends} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#263345" />
                    <XAxis dataKey="date" stroke="#677b95" fontSize={11} tickFormatter={formatDate} />
                    <YAxis stroke="#677b95" fontSize={11} />
                    <Tooltip
                      contentStyle={{ background: '#1c2430', border: '1px solid #37475e', borderRadius: 4 }}
                      labelStyle={{ color: '#e6edf5' }}
                    />
                    <Line type="monotone" dataKey="total_events" name="Total Events" stroke="#2da1bb" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="anomalous_events" name="Anomalous Signals" stroke="#e04b4b" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Tables Row: Highest Risk Users & Recent Alerts */}
          <div className="dashboard-tables-grid">
            {/* Highest Risk Users */}
            <div className="card dashboard-table-card">
              <div className="table-card-header">
                <div>
                  <h3 className="chart-title">Highest Risk Users</h3>
                  <span className="chart-subtitle text-muted">Top behavioral threat indicators</span>
                </div>
                <Link to="/users?sort_by=risk&sort_dir=desc" className="view-all-link">
                  <span>View All</span>
                  <ArrowRight size={14} />
                </Link>
              </div>

              {data.highest_risk_users.length === 0 ? (
                <div className="table-empty-msg text-muted">No high-risk users detected.</div>
              ) : (
                <div className="table-responsive">
                  <table className="compact-table">
                    <thead>
                      <tr>
                        <th>User ID</th>
                        <th>Department</th>
                        <th>Risk Score</th>
                        <th>Level</th>
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
                          <td className="font-mono font-bold">{u.user_id}</td>
                          <td>{u.department || '—'}</td>
                          <td className="font-mono">{formatRiskScore(u.hybrid_risk_score)}</td>
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

            {/* Recent Alerts */}
            <div className="card dashboard-table-card">
              <div className="table-card-header">
                <div>
                  <h3 className="chart-title">Recent Security Alerts</h3>
                  <span className="chart-subtitle text-muted">Unresolved and recent triage events</span>
                </div>
                <Link to="/alerts" className="view-all-link">
                  <span>View Queue</span>
                  <ArrowRight size={14} />
                </Link>
              </div>

              {data.recent_alerts.length === 0 ? (
                <div className="table-empty-msg text-muted">No security alerts triggered.</div>
              ) : (
                <div className="table-responsive">
                  <table className="compact-table">
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>User</th>
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
                          <td className="font-mono">{a.user_id}</td>
                          <td className="reason-cell" title={a.reason}>
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
