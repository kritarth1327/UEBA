import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  User as UserIcon,
  Building,
  Mail,
  Shield,
  Clock,
  Calendar,
  AlertTriangle,
  TrendingUp,
  Cpu,
  Layers,
  FileText,
  Activity,
  HardDrive,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
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
import './UserInvestigationPage.css';

export function UserInvestigationPage() {
  const { userId } = useParams();
  const navigate = useNavigate();

  const [user, setUser] = useState(null);
  const [behavior, setBehavior] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Date filters
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const fetchInvestigationData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [uRes, bRes, rRes, aRes] = await Promise.all([
        api.getUserDetail(userId),
        api.getUserBehavior(userId, {
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        }),
        api.getUserRisk(userId, {
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        }),
        api.getAlerts({ user_id: userId }),
      ]);

      setUser(uRes);
      setBehavior(bRes);
      setRiskData(rRes);
      setAlerts(aRes?.items || []);
    } catch (err) {
      setError(err.message || 'Failed to load user investigation data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userId) {
      fetchInvestigationData();
    }
  }, [userId, startDate, endDate]);

  if (loading) {
    return <LoadingSpinner message={`Loading investigation dossier for ${userId}...`} />;
  }

  if (error) {
    return (
      <div className="investigation-page">
        <button type="button" className="btn btn-secondary btn-sm back-btn" onClick={() => navigate('/users')}>
          <ArrowLeft size={14} />
          <span>Back to Users</span>
        </button>
        <ErrorAlert message={error} onRetry={fetchInvestigationData} />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="investigation-page">
        <button type="button" className="btn btn-secondary btn-sm back-btn" onClick={() => navigate('/users')}>
          <ArrowLeft size={14} />
          <span>Back to Users</span>
        </button>
        <EmptyState
          icon={UserIcon}
          title={`User ${userId} Not Found`}
          description="The requested user identifier does not exist in the database."
          actionLabel="View All Users"
          onAction={() => navigate('/users')}
        />
      </div>
    );
  }

  const latestPred = riskData?.latest_prediction;
  const behaviorProfiles = behavior?.profiles || [];
  const riskHistory = riskData?.history || [];

  return (
    <div className="investigation-page">
      {/* Top Navigation */}
      <div className="investigation-top-bar">
        <button type="button" className="btn btn-secondary btn-sm back-btn" onClick={() => navigate('/users')}>
          <ArrowLeft size={14} />
          <span>Back to Directory</span>
        </button>
        <span className="font-mono text-muted">ID: {user.user_id}</span>
      </div>

      {/* User Header Profile Card */}
      <div className="card user-profile-card">
        <div className="profile-left">
          <div className="profile-avatar">
            <UserIcon size={30} className="avatar-icon" />
          </div>
          <div className="profile-meta">
            <div className="profile-title-row">
              <h2 className="profile-name">
                {user.employee_name || user.user_id}
              </h2>
              <span className={`badge ${getRiskBadgeClass(user.latest_risk_level)}`}>
                {user.latest_risk_level || 'UNASSESSED'}
              </span>
            </div>
            <div className="profile-details-grid">
              <div className="detail-item">
                <span className="detail-label">Identifier:</span>
                <span className="detail-val font-mono">{user.user_id}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Department:</span>
                <span className="detail-val">{user.department || '—'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Role:</span>
                <span className="detail-val">{user.role || '—'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Supervisor:</span>
                <span className="detail-val">{user.supervisor || '—'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Email:</span>
                <span className="detail-val">{user.email || '—'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Behavior Records:</span>
                <span className="detail-val font-mono">{user.total_profiles_count} Days</span>
              </div>
            </div>
          </div>
        </div>

        <div className="profile-risk-summary">
          <span className="risk-score-label">Latest Hybrid Risk Score</span>
          <div className="risk-score-display font-mono">
            {formatRiskScore(user.latest_risk_score)}
            <span className="risk-score-max">/100</span>
          </div>
          <span className="risk-score-date text-muted">
            Assessed: {formatDate(user.latest_assessment_date)}
          </span>
        </div>
      </div>

      {/* Date Filter Bar */}
      <div className="card date-filter-bar">
        <div className="filter-title-group">
          <Calendar size={16} className="text-muted" />
          <span className="filter-bar-title">Investigation Time Window</span>
        </div>
        <div className="date-inputs">
          <div className="date-field">
            <label className="date-label">From:</label>
            <input
              type="date"
              className="date-input"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div className="date-field">
            <label className="date-label">To:</label>
            <input
              type="date"
              className="date-input"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          {(startDate || endDate) && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setStartDate('');
                setEndDate('');
              }}
            >
              Reset Window
            </button>
          )}
        </div>
      </div>

      {/* Detection Signals & Model Breakdown Grid */}
      <div className="signals-grid">
        {/* ML Threat Score Card */}
        <div className="card signal-card">
          <div className="signal-header">
            <div className="signal-title-group">
              <Cpu size={16} className="signal-icon text-teal" />
              <span className="signal-title">Supervised ML Threat Score</span>
            </div>
            <span className="signal-badge text-muted">XGBoost / RF</span>
          </div>
          <div className="signal-value-area">
            {latestPred?.ml_threat_score !== null && latestPred?.ml_threat_score !== undefined ? (
              <span className="signal-number font-mono">
                {(latestPred.ml_threat_score * 100).toFixed(1)}%
              </span>
            ) : (
              <span className="signal-unavailable">Unavailable (Awaiting Training)</span>
            )}
          </div>
          <p className="signal-desc text-muted">
            Probability of malicious activity mapped against CERT threat scenarios.
          </p>
        </div>

        {/* ANN Anomaly Score Card */}
        <div className="card signal-card">
          <div className="signal-header">
            <div className="signal-title-group">
              <Layers size={16} className="signal-icon text-purple" />
              <span className="signal-title">Neural Autoencoder Anomaly</span>
            </div>
            <span className="signal-badge text-muted">Dense ANN</span>
          </div>
          <div className="signal-value-area">
            {latestPred?.ann_anomaly_score !== null && latestPred?.ann_anomaly_score !== undefined ? (
              <span className="signal-number font-mono">
                {latestPred.ann_anomaly_score.toFixed(4)}
              </span>
            ) : (
              <span className="signal-unavailable">Unavailable (Awaiting Training)</span>
            )}
          </div>
          <p className="signal-desc text-muted">
            Reconstruction error of daily activity through autoencoder trained on normal patterns.
          </p>
        </div>

        {/* Personalized Baseline Deviation Card */}
        <div className="card signal-card">
          <div className="signal-header">
            <div className="signal-title-group">
              <Activity size={16} className="signal-icon text-amber" />
              <span className="signal-title">Personal Baseline Deviation</span>
            </div>
            <span className="signal-badge text-muted">Z-Score Normal</span>
          </div>
          <div className="signal-value-area">
            {latestPred?.baseline_deviation_score !== null && latestPred?.baseline_deviation_score !== undefined ? (
              <span className="signal-number font-mono">
                {latestPred.baseline_deviation_score.toFixed(2)}σ
              </span>
            ) : (
              <span className="signal-unavailable">Unavailable (Awaiting Baseline)</span>
            )}
          </div>
          <p className="signal-desc text-muted">
            Statistical deviation calculated against this specific employee's historical baseline.
          </p>
        </div>
      </div>

      {/* Contributing Factors & Explanations */}
      {latestPred?.contributing_factors && latestPred.contributing_factors.length > 0 && (
        <div className="card explanation-card">
          <h3 className="section-title">Contributing Behavioral Factors & Deviations</h3>
          <p className="section-subtitle text-muted">
            Evidence identified by the hybrid risk engine explaining this assessment.
          </p>
          <div className="factors-table-wrapper">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Behavior Feature</th>
                  <th>Description</th>
                  <th>Observed Value</th>
                  <th>Baseline Value</th>
                  <th>Impact Weight</th>
                </tr>
              </thead>
              <tbody>
                {latestPred.contributing_factors.map((factor, idx) => (
                  <tr key={idx}>
                    <td className="font-mono font-bold">{factor.feature}</td>
                    <td>{factor.description}</td>
                    <td className="font-mono">{factor.observed_value}</td>
                    <td className="font-mono text-muted">{factor.baseline_value ?? '—'}</td>
                    <td className="font-mono text-teal">
                      {(factor.contribution_weight * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Historical Risk Timeline Chart */}
      <div className="card chart-section-card">
        <div className="section-header">
          <div>
            <h3 className="section-title">Risk Assessment History</h3>
            <p className="section-subtitle text-muted">
              Longitudinal progression of computed hybrid risk scores.
            </p>
          </div>
        </div>

        {riskHistory.length === 0 ? (
          <div className="no-data-notice text-muted">
            No historical risk assessments recorded for this user.
          </div>
        ) : (
          <div style={{ height: 240, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={riskHistory} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#263345" />
                <XAxis dataKey="date" stroke="#677b95" fontSize={11} tickFormatter={formatDate} />
                <YAxis domain={[0, 100]} stroke="#677b95" fontSize={11} />
                <Tooltip
                  contentStyle={{ background: '#1c2430', border: '1px solid #37475e', borderRadius: 4 }}
                  labelStyle={{ color: '#e6edf5' }}
                />
                <Line
                  type="monotone"
                  dataKey="hybrid_risk_score"
                  name="Hybrid Risk Score"
                  stroke="#e2753a"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Daily Activity Visualizer */}
      <div className="card chart-section-card">
        <div className="section-header">
          <div>
            <h3 className="section-title">Daily Behavioral Activity Logs</h3>
            <p className="section-subtitle text-muted">
              Aggregated daily event counts (Logons, After Hours, Removable Devices, External Emails).
            </p>
          </div>
        </div>

        {behaviorProfiles.length === 0 ? (
          <div className="no-data-notice text-muted">
            No behavioral profile records available for the selected period.
          </div>
        ) : (
          <div style={{ height: 260, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={behaviorProfiles} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#263345" />
                <XAxis dataKey="date" stroke="#677b95" fontSize={11} tickFormatter={formatDate} />
                <YAxis stroke="#677b95" fontSize={11} />
                <Tooltip
                  contentStyle={{ background: '#1c2430', border: '1px solid #37475e', borderRadius: 4 }}
                  labelStyle={{ color: '#e6edf5' }}
                />
                <Legend />
                <Bar dataKey="logon_count" name="Logons" fill="#2da1bb" />
                <Bar dataKey="after_hours_logons" name="After Hours" fill="#d99a26" />
                <Bar dataKey="removable_device_events" name="USB Devices" fill="#e04b4b" />
                <Bar dataKey="email_external_count" name="External Emails" fill="#8497ad" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Related Alerts Table */}
      <div className="card related-alerts-card">
        <h3 className="section-title">Related Security Alerts</h3>
        <p className="section-subtitle text-muted">
          Incidents generated by detection thresholds for {user.user_id}.
        </p>

        {alerts.length === 0 ? (
          <div className="no-data-notice text-muted">
            No security alerts have been generated for this employee.
          </div>
        ) : (
          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Date</th>
                  <th>Reason</th>
                  <th>Risk Score</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>
                      <span className={`badge ${getSeverityBadgeClass(alert.severity)}`}>
                        {alert.severity}
                      </span>
                    </td>
                    <td>{formatDate(alert.date)}</td>
                    <td>{alert.reason}</td>
                    <td className="font-mono">{formatRiskScore(alert.risk_score)}</td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(alert.status)}`}>
                        {alert.status}
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
  );
}
