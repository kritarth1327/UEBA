import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Layers,
  GitBranch,
  Activity,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileCode,
  Shield,
  HelpCircle,
  Zap,
  Sliders,
  Scale,
} from 'lucide-react';
import { api } from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import './ModelsPage.css';

export function ModelsPage() {
  const [statusData, setStatusData] = useState(null);
  const [evalData, setEvalData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchModelInfo = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sRes, eRes] = await Promise.all([
        api.getModelsStatus(),
        api.getModelsEvaluation(),
      ]);
      setStatusData(sRes);
      setEvalData(eRes);
    } catch (err) {
      setError(err.message || 'Failed to retrieve model telemetry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModelInfo();
  }, []);

  if (loading) {
    return <LoadingSpinner message="Inspecting detection architectures and experiment records..." />;
  }

  if (error) {
    return <ErrorAlert message={error} onRetry={fetchModelInfo} />;
  }

  const models = statusData?.models || [];
  const evaluations = evalData?.evaluations || [];
  const hasEvaluations = evalData?.status === 'ready';
  const modelStatus = (name) => models.find((model) => model.model_name === name);
  const xgboost = modelStatus('XGBoost Supervised Threat Classifier');
  const ann = modelStatus('Dense Autoencoder Anomaly Detector');
  const cert = modelStatus('CERT Supervised Classifier');

  return (
    <div className="models-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Detection Models & Empirical Evaluation</h1>
          <p className="page-subtitle">
            Inspection of supervised machine learning classifiers, dense autoencoders, baseline deviations, and multi-signal risk fusion.
          </p>
        </div>

        <div className="models-status-pill font-mono">
          {statusData?.all_models_ready ? (
            <span className="badge badge-low">All Inference Engines Active</span>
          ) : statusData?.pipeline_ready ? (
            <span className="badge badge-medium">Partial Inference Available</span>
          ) : (
            <span className="badge badge-critical">No Inference Engines Available</span>
          )}
        </div>
      </div>

      {/* Architecture Cards Grid */}
      <div className="models-grid">
        {/* Model 1: Random Forest Baseline */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <GitBranch size={19} className="text-teal" />
            </div>
            <div>
              <h3 className="model-title">Random Forest Baseline</h3>
              <span className="model-framework font-mono text-muted">Scikit-Learn 1.9.1 &bull; Baseline</span>
            </div>
          </div>
          <p className="model-desc">
            Ensemble bagged decision forest serving as the classical tabular reference. Classifies user-day behavioral vectors against labeled threat scenarios.
          </p>
          <div className="model-specs">
            <div className="spec-row">
              <span className="spec-key">Role:</span>
              <span className="spec-val">Supervised Reference Classifier</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Input Features:</span>
              <span className="spec-val font-mono">User-Day Aggregated Counts</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Hyperparameters:</span>
              <span className="spec-val font-mono">n_estimators=100, max_depth=12</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Readiness:</span>
              <span className="spec-val text-muted">Reference artifact unavailable</span>
            </div>
          </div>
        </div>

        {/* Model 2: XGBoost Classifier */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <Cpu size={19} className="text-amber" />
            </div>
            <div>
              <h3 className="model-title">XGBoost Threat Classifier</h3>
              <span className="model-framework font-mono text-muted">XGBoost 3.4.1 &bull; Signal 1</span>
            </div>
          </div>
          <p className="model-desc">
            Gradient boosted decision tree producing continuous calibrated threat probabilities [0, 1]. Optimized for sparse, multi-source enterprise logs.
          </p>
          <div className="model-specs">
            <div className="spec-row">
              <span className="spec-key">Role:</span>
              <span className="spec-val">Primary Supervised Threat Detector</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Objective:</span>
              <span className="spec-val font-mono">binary:logistic</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Signal Weight:</span>
              <span className="spec-val font-mono font-bold text-teal">0.3825 (38.25%)</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Readiness:</span>
              <span className={`spec-val ${xgboost?.is_ready ? 'text-teal' : 'text-muted'}`}>
                {xgboost?.is_ready ? 'Loaded and ready' : 'Unavailable'}
              </span>
            </div>
          </div>
        </div>

        {/* Model 3: CERT Supervised Classifier */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <Shield size={19} className="text-amber" />
            </div>
            <div>
              <h3 className="model-title">CERT Supervised Classifier</h3>
              <span className="model-framework font-mono text-muted">XGBoost 3.4.1 &bull; CERT r4.2</span>
            </div>
          </div>
          <p className="model-desc">
            CERT-specific incident-window proxy classifier. Scores only profiles containing its complete 11-feature input contract.
          </p>
          <div className="model-specs">
            <div className="spec-row">
              <span className="spec-key">Role:</span>
              <span className="spec-val">CERT Supervised Signal</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Signal Weight:</span>
              <span className="spec-val font-mono font-bold text-teal">0.15 (15%)</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Readiness:</span>
              <span className={`spec-val ${cert?.is_ready ? 'text-teal' : 'text-muted'}`}>
                {cert?.is_ready ? 'Loaded and ready' : 'Unavailable'}
              </span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Label caveat:</span>
              <span className="spec-val text-muted">Incident-window proxy labels</span>
            </div>
          </div>
        </div>

        {/* Model 3: Dense Autoencoder */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <Layers size={19} className="text-purple" />
            </div>
            <div>
              <h3 className="model-title">Dense Autoencoder</h3>
              <span className="model-framework font-mono text-muted">PyTorch 2.14.1 &bull; Signal 2</span>
            </div>
          </div>
          <p className="model-desc">
            Artificial Neural Network trained strictly on benign baseline profiles. Reconstructs normal activity; unseen attack patterns produce high MSE loss.
          </p>
          <div className="model-specs">
            <div className="spec-row">
              <span className="spec-key">Architecture:</span>
              <span className="spec-val font-mono">Dense(32 &rarr; 16 &rarr; 8 &rarr; 16 &rarr; 32)</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Activations:</span>
              <span className="spec-val font-mono">ReLU Hidden &bull; MSE Loss</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Signal Weight:</span>
              <span className="spec-val font-mono font-bold text-teal">0.2975 (29.75%)</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Readiness:</span>
              <span className={`spec-val ${ann?.is_ready ? 'text-teal' : 'text-muted'}`}>
                {ann?.is_ready ? 'Loaded and ready' : 'Unavailable for profiles missing required features'}
              </span>
            </div>
          </div>
        </div>

        {/* Model 4: Hybrid Risk Engine */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <Scale size={19} className="text-teal" />
            </div>
            <div>
              <h3 className="model-title">Hybrid Risk Engine</h3>
              <span className="model-framework font-mono text-muted">Multi-Signal Calibrated Fusion</span>
            </div>
          </div>
          <p className="model-desc">
            Mathematical fusion engine synthesizing supervised threat probabilities, neural reconstruction loss, and personal longitudinal baseline deviations.
          </p>
          <div className="model-specs">
            <div className="spec-row">
              <span className="spec-key">Signals:</span>
              <span className="spec-val">Supervised ML + ANN + Baseline</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Classification:</span>
              <span className="spec-val font-mono">High &ge; 70 &bull; Med &ge; 40 &bull; Low &lt; 40</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Explainability:</span>
              <span className="spec-val">Ranked Contributing Feature Weights</span>
            </div>
            <div className="spec-row">
              <span className="spec-key">Status:</span>
              <span className="spec-val text-teal font-medium">
                {statusData?.pipeline_ready ? 'Partial fusion active' : 'Unavailable'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Empirical Evaluation Matrix Section */}
      <div className="card eval-section-card">
        <div className="eval-header-strip">
          <div>
            <h3 className="section-title">Experimental Evaluation Matrix</h3>
            <p className="section-subtitle text-muted">
              Performance metrics are measured on reserved CERT test splits using incident-window proxy labels; they do not establish validated real-world insider-threat detection performance.
            </p>
          </div>
          <span className={`badge ${hasEvaluations ? 'badge-low' : 'badge-neutral'}`}>
            {hasEvaluations ? 'Metrics available' : 'Evaluation unavailable'}
          </span>
        </div>

        {!hasEvaluations ? (
          <div className="eval-pending-box">
            <AlertCircle size={20} className="pending-icon text-muted" />
            <div className="pending-content">
              <h4 className="pending-heading">No Model Evaluation Metrics Available</h4>
              <p className="pending-text text-muted">
                In strict adherence to experimental research integrity, metrics are populated only from reserved CERT test runs using incident-window proxy labels. They are not validated real-world insider-threat performance claims, and no fabricated or hypothetical metrics are presented.
              </p>
            </div>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Detection Model</th>
                  <th>Version</th>
                  <th>Dataset Split</th>
                  <th>Accuracy</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1 Score</th>
                  <th>ROC-AUC</th>
                  <th>PR-AUC</th>
                </tr>
              </thead>
              <tbody>
                {evaluations.map((ev, idx) => (
                  <tr key={idx}>
                    <td className="font-bold text-primary">{ev.model_name}</td>
                    <td className="font-mono text-muted">{ev.version}</td>
                    <td className="font-mono">{ev.split}</td>
                    <td className="font-mono">{ev.accuracy !== null ? ev.accuracy.toFixed(4) : '—'}</td>
                    <td className="font-mono">{ev.precision !== null ? ev.precision.toFixed(4) : '—'}</td>
                    <td className="font-mono">{ev.recall !== null ? ev.recall.toFixed(4) : '—'}</td>
                    <td className="font-mono">{ev.f1_score !== null ? ev.f1_score.toFixed(4) : '—'}</td>
                    <td className="font-mono">{ev.roc_auc !== null ? ev.roc_auc.toFixed(4) : '—'}</td>
                    <td className="font-mono">{ev.pr_auc !== null ? ev.pr_auc.toFixed(4) : '—'}</td>
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
