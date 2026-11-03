import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
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
  Info,
  Sliders,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  ExternalLink,
  Zap,
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
  AreaChart,
  Area,
} from 'recharts';
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
import './UserInvestigationPage.css';

export function UserInvestigationPage() {
  const { userId } = useParams();
  const navigate = useNavigate();

  const [user, setUser] = useState(null);
  const [behavior, setBehavior] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [baselineData, setBaselineData] = useState(null);
  const [alerts, setAlerts] = useState([]);
  // Results from the trained dense autoencoder
  const [annData, setAnnData] = useState(null);
  const [annError, setAnnError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Date filters
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [datePreset, setDatePreset] = useState('all');

  // Selected Day for Inspection
  const [selectedDayDate, setSelectedDayDate] = useState(null);

  // Tab for evidence / timeline
  const [activeTab, setActiveTab] = useState('overview');

  const fetchInvestigationData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [uRes, bRes, rRes, aRes, blRes] = await Promise.all([
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
        api.getUserBaseline(userId).catch(() => null),
      ]);

      setUser(uRes);
      setBehavior(bRes);
      setRiskData(rRes);
      setAlerts(aRes?.items || []);
<<      // Store the backend personal baseline response.
      setBaselineData(blRes);

      // Fetch ANN scores independently so ANN failures don't break
      // the rest of the investigation page.
      try {
        const annRes = await api.getUserAnomalies(userId, {
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          limit: 1000,
        });

        setAnnData(annRes);
        setAnnError(null);
      } catch (annErr) {
        setAnnData(null);
        setAnnError(
          annErr.message || 'Unable to retrieve ANN anomaly results.'
        );
        console.error('ANN anomaly request failed:', annErr);
      }

      if (bRes?.profiles?.length > 0 && !selectedDayDate) {
        setSelectedDayDate(bRes.profiles[bRes.profiles.length - 1].date);
      }
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

  const handlePresetChange = (preset) => {
    setDatePreset(preset);
    const now = new Date();
    if (preset === '7d') {
      const d = new Date();
      d.setDate(now.getDate() - 7);
      setStartDate(d.toISOString().split('T')[0]);
      setEndDate(now.toISOString().split('T')[0]);
    } else if (preset === '30d') {
      const d = new Date();
      d.setDate(now.getDate() - 30);
      setStartDate(d.toISOString().split('T')[0]);
      setEndDate(now.toISOString().split('T')[0]);
    } else {
      setStartDate('');
      setEndDate('');
    }
  };

  if (loading) {
    return <LoadingSpinner message={`Compiling behavioral dossier for entity ${userId}...`} />;
  }

  if (error) {
    return (
      <div className="investigation-page">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/users')}>
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
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/users')}>
          <ArrowLeft size={14} />
          <span>Back to Users</span>
        </button>
        <EmptyState
          icon={UserIcon}
          title={`Entity ${userId} Not Found`}
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

  // ANN results returned by the trained autoencoder
  const annResults = annData?.results || [];

  // Use the latest available result by date.
  const latestAnn = [...annResults].sort((a, b) =>
    String(b.date).localeCompare(String(a.date))
  )[0] || null;

  // Match the ANN score to the currently selected behavioral day.
  const activeAnn = selectedDayDate
    ? annResults.find((result) => result.date === selectedDayDate) || null
    : latestAnn;
  // Selected day profile
  const activeProfile = selectedDayDate
    ? behaviorProfiles.find((p) => p.date === selectedDayDate) || behaviorProfiles[behaviorProfiles.length - 1]
    : behaviorProfiles[behaviorProfiles.length - 1];
      // Calculate personal baselines using only profiles before the selected day.
  // This prevents the day being investigated from influencing its own baseline.
  const baselineProfiles = activeProfile
  ? behaviorProfiles.filter(
      (profile) => String(profile.date) < String(activeProfile.date)
    )
  : [];

const getBaselineStats = (feature) => {
  const values = baselineProfiles
    .map((profile) => Number(profile[feature]))
    .filter((value) => Number.isFinite(value));

  if (values.length === 0) {
    return null;
  }

  const mean =
    values.reduce((sum, value) => sum + value, 0) / values.length;

  const variance =
    values.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
    values.length;

  return {
    mean,
    std: Math.sqrt(variance),
    count: values.length,
  };
};

const getDeviation = (observed, stats) => {
  if (!stats || stats.std === 0) {
    return null;
  }

  return (Number(observed) - stats.mean) / stats.std;
};

const baselineFeatures = {
  logon_count: getBaselineStats('logon_count'),
  after_hours_logons: getBaselineStats('after_hours_logons'),
  removable_device_events: getBaselineStats('removable_device_events'),
  email_external_count: getBaselineStats('email_external_count'),
  total_session_duration: getBaselineStats('total_session_duration'),
};

  return (
    <div className="investigation-page">
      {/* Top Breadcrumb & Controls */}
      <div className="investigation-top-bar">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/users')}>
          <ArrowLeft size={13} />
          <span>Back to Entity Directory</span>
        </button>

        <div className="investigation-mode-badge font-mono">
          <Shield size={13} className="text-teal" />
          <span>INVESTIGATION CONSOLE</span>
        </div>
      </div>

      {/* Entity Profile Header Card */}
      <div className="card entity-header-card">
        <div className="entity-left">
          <div className="entity-avatar font-mono">
            {user.user_id.slice(0, 3)}
          </div>
          <div className="entity-info-block">
            <div className="entity-name-row">
              <h2 className="entity-name">{user.employee_name || user.user_id}</h2>
              <span className={`badge ${getRiskBadgeClass(user.latest_risk_level)}`}>
                {user.latest_risk_level || 'UNASSESSED'}
              </span>
              <span className="badge badge-neutral font-mono">{user.user_id}</span>
            </div>

            <div className="entity-meta-grid">
              <div className="meta-cell">
                <span className="meta-cell-label">Department</span>
                <span className="meta-cell-val">{user.department || '—'}</span>
              </div>
              <div className="meta-cell">
                <span className="meta-cell-label">Role</span>
                <span className="meta-cell-val">{user.role || '—'}</span>
              </div>
              <div className="meta-cell">
                <span className="meta-cell-label">Supervisor</span>
                <span className="meta-cell-val">{user.supervisor || '—'}</span>
              </div>
              <div className="meta-cell">
                <span className="meta-cell-label">Corporate Email</span>
                <span className="meta-cell-val font-mono">{user.email || '—'}</span>
              </div>
              <div className="meta-cell">
                <span className="meta-cell-label">Observed History</span>
                <span className="meta-cell-val font-mono font-medium">{user.total_profiles_count} Days</span>
              </div>
              <div className="meta-cell">
                <span className="meta-cell-label">Active Alerts</span>
                <span className="meta-cell-val font-mono font-bold text-amber">{user.total_alerts_count}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Large Risk Metric Score Box */}
        <div className="entity-risk-box">
          <span className="risk-metric-title">HYBRID RISK INDEX</span>
          <div className="risk-score-wrapper font-mono">
            <span className="risk-score-number">{formatRiskScore(user.latest_risk_score)}</span>
            <span className="risk-score-total">/100</span>
          </div>
          <div className="risk-score-subtitle text-muted">
            Last evaluated: {formatDate(user.latest_assessment_date)}
          </div>
        </div>
      </div>

      {/* Date Range & Preset Filter Bar */}
      <div className="card date-filter-panel">
        <div className="date-filter-left">
          <Calendar size={15} className="text-teal" />
          <span className="filter-title">Observation Time Window:</span>
          <div className="tab-group">
            <button
              type="button"
              className={`tab-btn ${datePreset === 'all' ? 'tab-btn-active' : ''}`}
              onClick={() => handlePresetChange('all')}
            >
              All Records
            </button>
            <button
              type="button"
              className={`tab-btn ${datePreset === '30d' ? 'tab-btn-active' : ''}`}
              onClick={() => handlePresetChange('30d')}
            >
              Last 30 Days
            </button>
            <button
              type="button"
              className={`tab-btn ${datePreset === '7d' ? 'tab-btn-active' : ''}`}
              onClick={() => handlePresetChange('7d')}
            >
              Last 7 Days
            </button>
          </div>
        </div>

        <div className="date-filter-inputs">
          <div className="input-group">
            <label className="input-label">From</label>
            <input
              type="date"
              className="date-input-field"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setDatePreset('custom');
              }}
            />
          </div>
          <div className="input-group">
            <label className="input-label">To</label>
            <input
              type="date"
              className="date-input-field"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setDatePreset('custom');
              }}
            />
          </div>
          {(startDate || endDate) && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => handlePresetChange('all')}
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Detection Triad (The 3 Model Signals) + Risk Fusion Formula */}
      <div className="detection-triad-grid">
        {/* Signal 1: Supervised ML */}
        <div className="card signal-card">
          <div className="signal-card-header">
            <div className="signal-title-box">
              <Cpu size={16} className="text-teal" />
              <div>
                <h4 className="signal-name">Supervised ML Threat Score</h4>
                <span className="signal-tech text-muted">XGBoost • Scenario Mapping</span>
              </div>
            </div>
            <span className="badge badge-teal">Signal 1</span>
          </div>

          <div className="signal-metric-area">
            {latestPred?.ml_threat_score !== null && latestPred?.ml_threat_score !== undefined ? (
              <div className="signal-metric-val font-mono">
                {(latestPred.ml_threat_score * 100).toFixed(1)}%
              </div>
            ) : (
              <div className="signal-unavailable-text">
                <Clock size={13} />
                <span>Unavailable (Awaiting Model Training)</span>
              </div>
            )}
          </div>
          <p className="signal-explanation text-muted">
            Calibrated threat probability calculated against known insider threat scenarios in CERT training splits.
          </p>
          <div className="signal-weight-row">
            <span className="weight-label">Engine Weight:</span>
            <span className="weight-val font-mono">45% (0.45)</span>
          </div>
        </div>

        {/* Signal 2: Dense Autoencoder (ANN) */}
        <div className="card signal-card">
          <div className="signal-card-header">
            <div className="signal-title-box">
              <Layers size={16} className="text-purple" />
              <div>
                <h4 className="signal-name">Neural Autoencoder Anomaly</h4>
                <span className="signal-tech text-muted">Dense ANN • Reconstruction MSE</span>
              </div>
            </div>
            <span className="badge badge-neutral">Signal 2</span>
          </div>

          <div className="signal-metric-area">
            {latestAnn ? (
              <>
                <div className="signal-metric-val font-mono">
                  {Number(latestAnn.ann_anomaly_score).toFixed(6)}
                </div>

                <div style={{ marginTop: 8 }}>
                  <span
                    className={`badge ${
                      latestAnn.is_anomaly_candidate
                        ? 'badge-critical'
                        : 'badge-low'
                    }`}
                  >
                    {latestAnn.is_anomaly_candidate
                      ? 'Anomaly Candidate'
                      : 'Below Threshold'}
                  </span>
                </div>

                <div className="text-muted" style={{ marginTop: 8, fontSize: 12 }}>
                  Threshold: {Number(latestAnn.threshold).toFixed(6)}
                </div>

                <div className="text-muted" style={{ marginTop: 4, fontSize: 12 }}>
                  Observed: {formatDate(latestAnn.date)}
                </div>
              </>
            ) : (
              <div className="signal-unavailable-text">
                <Clock size={13} />
                <span>
                  {annError
                    ? 'ANN results unavailable'
                    : 'No ANN results available'}
                </span>
              </div>
            )}
          </div>
          <p className="signal-explanation text-muted">
            Reconstruction error of daily vector passed through autoencoder trained exclusively on benign behavior.
          </p>
          <div className="signal-weight-row">
            <span className="weight-label">Engine Weight:</span>
            <span className="weight-val font-mono">35% (0.35)</span>
          </div>
        </div>

        {/* Signal 3: Longitudinal Baseline */}
        <div className="card signal-card">
          <div className="signal-card-header">
            <div className="signal-title-box">
              <Activity size={16} className="text-amber" />
              <div>
                <h4 className="signal-name">Personal Baseline Deviation</h4>
                <span className="signal-tech text-muted">Z-Score Normal • Per-User</span>
              </div>
            </div>
            <span className="badge badge-neutral">Signal 3</span>
          </div>

          <div className="signal-metric-area">
            {latestPred?.baseline_deviation_score !== null && latestPred?.baseline_deviation_score !== undefined ? (
              <div className="signal-metric-val font-mono">
                {latestPred.baseline_deviation_score.toFixed(2)}σ
              </div>
            ) : (
              <div className="signal-unavailable-text">
                <Clock size={13} />
                <span>Unavailable (Awaiting Baseline Window)</span>
              </div>
            )}
          </div>
          <p className="signal-explanation text-muted">
            Standard deviation units relative to this employee's personal historical baseline mean.
          </p>
          <div className="signal-weight-row">
            <span className="weight-label">Engine Weight:</span>
            <span className="weight-val font-mono">20% (0.20)</span>
          </div>
        </div>
      </div>

      {/* Fusion Engine Explainability Box */}
      <div className="card fusion-formula-card">
        <div className="formula-header">
          <Zap size={16} className="text-teal" />
          <h4 className="formula-title">Hybrid Risk Fusion Engine Calibration</h4>
        </div>
        <p className="formula-desc text-muted">
          Final threat assessment combines supervised detection of known threat signatures with unsupervised detection of novel anomalies and per-user personal baseline deviations:
        </p>
        <div className="formula-display font-mono">
          <span className="formula-accent">Hybrid Score [0-100]</span> = 100 × (0.45 × S_ML + 0.35 × S_ANN + 0.20 × S_Baseline)
        </div>
        <div className="formula-thresholds">
          <span className="thresh-chip chip-low">• Low Risk: &lt; 40</span>
          <span className="thresh-chip chip-med">• Medium Risk: 40 – 69</span>
          <span className="thresh-chip chip-high">• High Risk: ≥ 70</span>
        </div>
      </div>

      {/* Behavioral Activity Timeline */}
      <div className="card section-card">
        <div className="section-card-header">
          <div>
            <h3 className="section-title">Daily Behavioral Activity Timeline</h3>
            <span className="section-subtitle text-muted">
              Click any day in the timeline below to inspect the exact behavioral metrics recorded for that day.
            </span>
          </div>
          {selectedDayDate && (
            <span className="selected-day-tag font-mono">
              Selected: {formatDate(selectedDayDate)}
            </span>
          )}
        </div>

        {behaviorProfiles.length === 0 ? (
          <div className="table-empty-notice text-muted">
            No behavioral profile records available for the selected period.
          </div>
        ) : (
          <div style={{ height: 250, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={behaviorProfiles}
                margin={{ top: 10, right: 24, left: -10, bottom: 0 }}
                onClick={(e) => {
                  if (e && e.activeLabel) {
                    setSelectedDayDate(e.activeLabel);
                  }
                }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#edf2f7" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickFormatter={formatDate} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: 12, boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}
                  labelStyle={{ color: '#0f172a', fontWeight: 600 }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                <Bar dataKey="logon_count" name="Logons" fill="#0891b2" radius={[3, 3, 0, 0]} />
                <Bar dataKey="after_hours_logons" name="Off-Hours Logons" fill="#b45309" radius={[3, 3, 0, 0]} />
                <Bar dataKey="removable_device_events" name="USB Devices" fill="#991b1b" radius={[3, 3, 0, 0]} />
                <Bar dataKey="email_external_count" name="External Emails" fill="#64748b" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ANN Reconstruction Error Timeline */}
      <div className="card section-card">
        <div className="section-card-header">
          <div>
            <h3 className="section-title">
              ANN Anomaly Detection Timeline
            </h3>

            <span className="section-subtitle text-muted">
              Daily reconstruction errors compared against the trained model's
              validation threshold.
            </span>
          </div>

          {annData && (
            <span className="badge badge-neutral">
              {annData.anomaly_candidates} candidates
            </span>
          )}
        </div>

        {annError ? (
          <div className="table-empty-notice text-muted">
            {annError}
          </div>
        ) : annResults.length === 0 ? (
          <div className="table-empty-notice text-muted">
            No ANN results available for the selected period.
          </div>
        ) : (
          <>
            <div style={{ height: 260, width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={[...annResults].sort((a, b) =>
                    String(a.date).localeCompare(String(b.date))
                  )}
                  margin={{ top: 10, right: 24, left: 12, bottom: 0 }}
                  onClick={(event) => {
                    if (event?.activeLabel) {
                      setSelectedDayDate(event.activeLabel);
                    }
                  }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#edf2f7" />

                  <XAxis
                    dataKey="date"
                    stroke="#94a3b8"
                    fontSize={11}
                    tickFormatter={formatDate}
                  />

                  <YAxis
                    stroke="#94a3b8"
                    fontSize={11}
                    domain={[0, 'auto']}
                  />

                  <Tooltip
                    labelFormatter={(date) => `Date: ${formatDate(date)}`}
                    formatter={(value, name) => [
                      Number(value).toFixed(6),
                      name,
                    ]}
                  />

                  <Legend />

                  <Line
                    type="monotone"
                    dataKey="ann_anomaly_score"
                    name="Reconstruction Error"
                    stroke="#7c3aed"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 5 }}
                  />

                  <Line
                    type="monotone"
                    dataKey="threshold"
                    name="Detection Threshold"
                    stroke="#c2410c"
                    strokeWidth={2}
                    strokeDasharray="6 4"
                    dot={false}
                    activeDot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <p className="text-muted" style={{ fontSize: 12, marginTop: 12 }}>
              Profiles above the threshold are anomaly candidates, not
              confirmed malicious activity. Select a date on the chart to
              inspect that day's behavioral profile.
            </p>
          </>
        )}
      </div>

      {/* Day Inspector & Personal Baseline Comparison */}
      {activeProfile && (
        <div className="card section-card">
          <div className="section-card-header">
            <div>
              <h3 className="section-title">
                Personal Baseline Deviation Inspector • {formatDate(activeProfile.date)}
              </h3>
              <span className="section-subtitle text-muted">
                Observed enterprise activity compared against this user's established historical normal parameters.
              </span>
            </div>

            <div className="day-stepper font-mono">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={behaviorProfiles.findIndex((p) => p.date === activeProfile.date) <= 0}
                onClick={() => {
                  const idx = behaviorProfiles.findIndex((p) => p.date === activeProfile.date);
                  if (idx > 0) setSelectedDayDate(behaviorProfiles[idx - 1].date);
                }}
              >
                &larr; Prev Day
              </button>
              <select
                className="styled-select day-select"
                value={activeProfile.date}
                onChange={(e) => setSelectedDayDate(e.target.value)}
              >
                {behaviorProfiles.map((p) => (
                  <option key={p.date} value={p.date}>
                    {p.date}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={
                  behaviorProfiles.findIndex((p) => p.date === activeProfile.date) >=
                  behaviorProfiles.length - 1
                }
                onClick={() => {
                  const idx = behaviorProfiles.findIndex((p) => p.date === activeProfile.date);
                  if (idx < behaviorProfiles.length - 1) {
                    setSelectedDayDate(behaviorProfiles[idx + 1].date);
                  }
                }}
              >
                Next Day &rarr;
              </button>
            </div>
          </div>
                    {/* ANN result for the currently selected day */}
                    <div
            style={{
              marginBottom: 20,
              padding: 16,
              borderRadius: 10,
              border: `1px solid ${
                activeAnn?.is_anomaly_candidate ? '#fca5a5' : '#cbd5e1'
              }`,
              background: activeAnn?.is_anomaly_candidate
                ? '#fef2f2'
                : '#f8fafc',
            }}
          >
            <h4 style={{ margin: '0 0 12px', fontSize: 15 }}>
              Neural Autoencoder — Selected Day Assessment
            </h4>

            {activeAnn ? (
              <>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: 16,
                  }}
                >
                  <div>
                    <div className="text-muted" style={{ fontSize: 12 }}>
                      Selected Date
                    </div>
                    <div className="font-mono font-bold">
                      {formatDate(activeAnn.date)}
                    </div>
                  </div>

                  <div>
                    <div className="text-muted" style={{ fontSize: 12 }}>
                      Reconstruction Error
                    </div>
                    <div className="font-mono font-bold">
                      {Number(activeAnn.ann_anomaly_score).toFixed(6)}
                    </div>
                  </div>

                  <div>
                    <div className="text-muted" style={{ fontSize: 12 }}>
                      Detection Threshold
                    </div>
                    <div className="font-mono font-bold">
                      {Number(activeAnn.threshold).toFixed(6)}
                    </div>
                  </div>

                  <div>
                    <div className="text-muted" style={{ fontSize: 12 }}>
                      Detection Status
                    </div>
                    <div style={{ marginTop: 4 }}>
                      <span
                        className={`badge ${
                          activeAnn.is_anomaly_candidate
                            ? 'badge-critical'
                            : 'badge-low'
                        }`}
                      >
                        {activeAnn.is_anomaly_candidate
                          ? 'Anomaly Candidate'
                          : 'Below Threshold'}
                      </span>
                    </div>
                  </div>
                </div>

                <p
                  className="text-muted"
                  style={{ fontSize: 12, margin: '14px 0 0' }}
                >
                  {activeAnn.is_anomaly_candidate
                    ? 'This day exceeded the trained autoencoder threshold. Investigate the associated behavior before drawing conclusions.'
                    : 'This day did not exceed the trained autoencoder threshold. This does not guarantee that the activity is benign.'}
                </p>
              </>
            ) : (
              <p className="text-muted" style={{ fontSize: 13, margin: 0 }}>
                No ANN result is available for this date. Select a date with a
                matching ANN assessment to inspect its reconstruction error.
              </p>
            )}
          </div>

          {!baselineData?.has_baseline && (
            <div className="baseline-pending-callout">
              <Info size={16} className="text-teal" style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong>Personal Baseline Status: Calibration Pending</strong>
                <p className="text-muted" style={{ margin: '2px 0 0', fontSize: '12px' }}>
                  A personal baseline requires a minimum of 14 observation days of ingested behavioral data. Once the CERT r4.2 pipeline processes multi-week behavior, moving statistics (mean, standard deviation, median, IQR) calibrate individual normal boundaries.
                </p>
              </div>
            </div>
          )}

          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Behavioral Dimension</th>
                  <th>Observed Day Count</th>
                  <th>Personal Baseline Mean</th>
                  <th>Standard Dev (&sigma;)</th>
                  <th>Calculated Deviation</th>
                  <th>Inspection Status</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { key: 'logon_count', label: 'System Logons', unit: '' },
                  { key: 'after_hours_logons', label: 'Off-Hours Logons', unit: '' },
                  { key: 'removable_device_events', label: 'Removable Media / USB Events', unit: '' },
                  { key: 'file_copied_removable', label: 'Files Copied to Removable Device', unit: '' },
                  { key: 'file_access_count', label: 'Sensitive Files Accessed', unit: '' },
                  { key: 'email_external_count', label: 'External Email Transmissions', unit: '' },
                  { key: 'email_attachment_count', label: 'Email Attachments Sent', unit: '' },
                  { key: 'http_after_hours_count', label: 'Off-Hours HTTP Web Requests', unit: '' },
                  { key: 'total_session_duration', label: 'Total Active Session Duration', unit: ' hrs', isFloat: true },
                ]
                  .filter((dim) =>
                    activeProfile[dim.key] !== undefined &&
                    activeProfile[dim.key] !== null
                  )
                  .map((dim) => {
                    const obsVal = Number(activeProfile[dim.key]);
                    const displayObs = dim.isFloat
                      ? `${obsVal.toFixed(1)}${dim.unit}`
                      : `${obsVal}${dim.unit}`;

                    const bMetric = baselineData?.baseline?.metrics?.[dim.key];
                    const hasBaseline =
                      baselineData?.has_baseline &&
                      bMetric &&
                      Number.isFinite(Number(bMetric.mean)) &&
                      Number.isFinite(Number(bMetric.std));

                    if (hasBaseline) {
                      const mean = Number(bMetric.mean);
                      const std = Number(bMetric.std);
                      const effectiveStd = std > 1e-4 ? std : 1.0;
                      const zScore = (obsVal - mean) / effectiveStd;

                      const isAnomalous = Math.abs(zScore) >= 2.5;
                      const isElevated =
                        Math.abs(zScore) >= 1.5 && Math.abs(zScore) < 2.5;

                      return (
                        <tr key={dim.key}>
                          <td className="font-medium text-primary">
                            {dim.label}
                          </td>
                          <td className={`font-mono font-bold ${
                            isAnomalous
                              ? 'text-critical'
                              : isElevated
                                ? 'text-amber'
                                : ''
                          }`}>
                            {displayObs}
                          </td>
                          <td className="font-mono text-muted">
                            {mean.toFixed(2)}{dim.unit}
                          </td>
                          <td className="font-mono text-muted">
                            {std.toFixed(2)}
                          </td>
                          <td className="font-mono font-semibold">
                            {zScore >= 0
                              ? `+${zScore.toFixed(2)}`
                              : zScore.toFixed(2)}&sigma;
                          </td>
                          <td>
                            {isAnomalous ? (
                              <span className="badge badge-critical">
                                Anomalous
                              </span>
                            ) : isElevated ? (
                              <span className="badge badge-medium">
                                Elevated
                              </span>
                            ) : (
                              <span className="badge badge-low">
                                Normal
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    }

                    return (
                      <tr key={dim.key}>
                        <td className="font-medium text-primary">
                          {dim.label}
                        </td>
                        <td className="font-mono font-bold">
                          {displayObs}
                        </td>
                        <td className="font-mono text-muted">—</td>
                        <td className="font-mono text-muted">—</td>
                        <td className="font-mono text-muted">—</td>
                        <td>
                          <span className="badge badge-neutral">
                            Observed (Uncalibrated)
                          </span>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!activeProfile && (
        <div className="card section-card">
          <div className="section-card-header">
            <div>
              <h3 className="section-title">Personal Baseline & Day Telemetry Inspector</h3>
              <span className="section-subtitle text-muted">
                Observed enterprise activity compared against this user's established historical normal parameters.
              </span>
            </div>
          </div>
          <div className="baseline-pending-callout">
            <Info size={16} className="text-teal" style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <strong>Awaiting Behavioral Telemetry Ingestion</strong>
              <p className="text-muted" style={{ margin: '2px 0 0', fontSize: '12px' }}>
                No daily behavioral activity records have been ingested for this entity yet. Once the CERT r4.2 ingestion pipeline processes employee activity logs (logon, device, file, email, http), day-by-day telemetry and personal baseline z-score deviations will be displayed here.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Contributing Factors & Explanations */}
      {latestPred?.contributing_factors && latestPred.contributing_factors.length > 0 && (
        <div className="card section-card">
          <div className="section-card-header">
            <div>
              <h3 className="section-title">Contributing Risk Factors & Evidence Traces</h3>
              <span className="section-subtitle text-muted">
                Behaviors that exerted the greatest positive weight on the calculated threat score.
              </span>
            </div>
          </div>

          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Factor Feature</th>
                  <th>Behavior Narrative</th>
                  <th>Observed Value</th>
                  <th>Baseline Reference</th>
                  <th>Impact Weight</th>
                </tr>
              </thead>
              <tbody>
                {latestPred.contributing_factors.map((factor, idx) => (
                  <tr key={idx}>
                    <td className="font-mono font-semibold text-primary">{factor.feature}</td>
                    <td className="font-medium">{factor.description}</td>
                    <td className="font-mono font-bold">{factor.observed_value}</td>
                    <td className="font-mono text-muted">{factor.baseline_value ?? '—'}</td>
                    <td className="font-mono text-teal font-semibold">
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
      <div className="card section-card">
        <div className="section-card-header">
          <div>
            <h3 className="section-title">Longitudinal Risk Score Progression</h3>
            <span className="section-subtitle text-muted">
              Trend of computed hybrid threat levels over the observation period.
            </span>
          </div>
        </div>

        {riskHistory.length === 0 ? (
          <div className="table-empty-notice text-muted">
            No historical risk assessments recorded for this entity.
          </div>
        ) : (
          <div style={{ height: 200, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={riskHistory} margin={{ top: 8, right: 24, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#edf2f7" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickFormatter={formatDate} />
                <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={11} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: 12, boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}
                  labelStyle={{ color: '#0f172a', fontWeight: 600 }}
                />
                <Line
                  type="monotone"
                  dataKey="hybrid_risk_score"
                  name="Hybrid Risk Score"
                  stroke="#c2410c"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#c2410c' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Linked Security Incidents */}
      <div className="card section-card">
        <div className="section-card-header">
          <div>
            <h3 className="section-title">Linked Incident Records & Alerts</h3>
            <span className="section-subtitle text-muted">
              Security incidents triggered for entity {user.user_id}.
            </span>
          </div>
        </div>

        {alerts.length === 0 ? (
          <div className="table-empty-notice text-muted">
            No security incidents have been triggered for this user.
          </div>
        ) : (
          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Detection Date</th>
                  <th>Reason</th>
                  <th>Risk Score</th>
                  <th>Status</th>
                  <th>Action</th>
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
                    <td className="text-muted">{formatDate(alert.date)}</td>
                    <td className="font-medium text-primary">{alert.reason}</td>
                    <td className="font-mono font-bold">{formatRiskScore(alert.risk_score)}</td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(alert.status)}`}>
                        {alert.status}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => navigate('/alerts')}
                      >
                        Triage Queue
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
  );
}
