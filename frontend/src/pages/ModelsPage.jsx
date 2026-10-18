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
      setError(err.message || 'Failed to retrieve model status.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModelInfo();
  }, []);

  if (loading) {
    return <LoadingSpinner message="Checking model readiness and evaluation artifacts..." />;
  }

  if (error) {
    return <ErrorAlert message={error} onRetry={fetchModelInfo} />;
  }

  const models = statusData?.models || [];
  const evaluations = evalData?.evaluations || [];
  const hasEvaluations = evalData?.status === 'ready';

  return (
    <div className="models-page">
      <div className="models-header">
        <div>
          <h1 className="models-title">Detection Models & Experimental Evaluation</h1>
          <p className="models-subtitle">
            Inspection of supervised ML, neural autoencoders, baseline deviations, and multi-signal risk fusion.
          </p>
        </div>

        <div className="models-status-pill">
          {statusData?.all_models_ready ? (
            <span className="badge badge-low">All Models Ready</span>
          ) : (
            <span className="badge badge-neutral">Awaiting CERT Training</span>
          )}
        </div>
      </div>

      {/* Model Architectures & Interfaces Grid */}
      <div className="models-grid">
        {/* Model 1: Random Forest Baseline */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <GitBranch size={20} className="model-icon text-teal" />
            </div>
            <div>
              <h3 className="model-name">Random Forest Baseline</h3>
              <span className="model-version text-muted">Version: 1.0.0 &bull; Scikit-Learn</span>
            </div>
          </div>
          <p className="model-description">
            Ensemble decision forest serving as the classical tabular baseline. Classifies daily feature vectors against ground truth threat scenarios.
          </p>
          <div className="model-meta-list">
            <div className="model-meta-row">
              <span className="meta-label">Target:</span>
              <span className="meta-val">Known threat scenarios</span>
            </div>
            <div className="model-meta-row">
              <span className="meta-label">Features:</span>
              <span className="meta-val">User-day aggregated counts</span>
            </div>
            <div className="model-meta-row">
              <span className="meta-label">Status:</span>
              <span className="meta-val text-muted">Awaiting dataset training</span>
            </div>
          </div>
        </div>

        {/* Model 2: XGBoost Classifier */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <Cpu size={20} className="model-icon text-amber" />
            </div>
            <div>
              <h3 className="model-name">XGBoost Threat Classifier</h3>
              <span className="model-version text-muted">Version: 1.0.0 &bull; XGBoost 3.4.1</span>
            </div>
          </div>
          <p className="model-description">
            Gradient boosted decision trees optimized for sparse multi-source enterprise activity logs. Generates calibrated threat probabilities [0, 1].
          </p>
          <div className="model-meta-list">
            <div className="model-meta-row">
              <span className="meta-label">Target:</span>
              <span className="meta-val">Threat classification & ranking</span>
            </div>
            <div className="model-meta-row">
              <span className="meta-label">Objective:</span>
              <span className="meta-val font-mono">binary:logistic</span>
            </div>
            <div className="model-meta-row">
              <span className="meta-label">Status:</span>
              <span className="meta-val text-muted">Awaiting dataset training</span>
            </div>
          </div>
        </div>

        {/* Model 3: Dense Autoencoder */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <Layers size={20} className="model-icon text-purple" />
            </div>
            <div>
              <h3 className="model-name">Dense Autoencoder</h3>
              <span className="model-version text-muted">Version: 1.0.0 &bull; PyTorch 2.14.1</span>
            </div>
          </div>
          <p className="model-description">
            Deep neural network trained exclusively on benign activity. Unseen attack patterns result in elevated reconstruction error (MSE).
          </p>
          <div className="model-meta-list">
            <div className="model-meta-row">
              <span className="meta-label">Architecture:</span>
              <span className="meta-val font-mono">32 &rarr; 16 &rarr; 8 &rarr; 16 &rarr; 32</span>
            </div>
            <div className="model-meta-row">
              <span className="meta-label">Activations:</span>
              <span className="meta-val font-mono">ReLU hidden</span>
            </div>
            <div className="model-meta-row">
              <span className="meta-label">Status:</span>
              <span className="meta-val text-muted">Awaiting normal profile training</span>
            </div>
          </div>
        </div>

        {/* Model 4: Hybrid Risk Engine */}
        <div className="card model-card">
          <div className="model-card-header">
            <div className="model-icon-box">
              <Shield size={20} className="model-icon text-teal" />
            </div>
            <div>
              <h3 className="model-name">Hybrid Risk Engine</h3>
              <span className="model-version text-muted">Multi-Signal Calibrated Fusion</span>
            </div>
          </div>
          <p className="model-description">
            Combines the Supervised ML threat probability, ANN reconstruction error, and per-user longitudinal baseline z-scores into an explainable score.
          </p>
          <div className="model-meta-list">
            <div className="model-meta-row">
              <span className="meta-label">Formula:</span>
              <span className="meta-val font-mono">w1&middot;ML + w2&middot;ANN + w3&middot;Baseline</span>
            </div>
            <div className="model-meta-row">
              <span className="meta-label">Thresholds:</span>
              <span className="meta-val font-mono">High &ge; 70 | Med &ge; 40</span>
            </div>
            <div className="model-meta-row">
              <span className="meta-label">Status:</span>
              <span className="meta-val text-muted">Active logic, awaiting model inputs</span>
            </div>
          </div>
        </div>
      </div>

      {/* Experimental Evaluation Matrix */}
      <div className="card evaluation-section-card">
        <div className="eval-header">
          <div>
            <h3 className="section-title">Model Evaluation Matrix</h3>
            <p className="section-subtitle text-muted">
              Empirical metrics measured against the ground truth test split.
            </p>
          </div>

          <span className={`badge ${hasEvaluations ? 'badge-low' : 'badge-neutral'}`}>
            {hasEvaluations ? 'Evaluated' : 'Evaluation Pending'}
          </span>
        </div>

        {!hasEvaluations ? (
          <div className="honest-pending-box">
            <AlertCircle size={20} className="pending-icon text-muted" />
            <div className="pending-text">
              <h4 className="pending-title">No Evaluation Results Available Yet</h4>
              <p className="pending-desc">
                Experimental results (Precision, Recall, F1, ROC-AUC, PR-AUC, Confusion Matrix) will be populated once models are trained and evaluated on the actual CERT Insider Threat Dataset r4.2. In compliance with strict research integrity, placeholder or fabricated metrics are never displayed.
              </p>
            </div>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Model</th>
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
                    <td className="font-bold">{ev.model_name}</td>
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
