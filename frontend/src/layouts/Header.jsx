import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Bell, ShieldCheck, AlertCircle, RefreshCw, Home, ChevronRight } from 'lucide-react';
import { api } from '../api/client';
import './Header.css';

const ROUTE_LABELS = {
  '/': 'Security Operations Overview',
  '/users': 'Entity Intelligence & User Directory',
  '/alerts': 'Alert Investigation Queue',
  '/models': 'Detection Models & Evaluation Matrix',
  '/system': 'Infrastructure & Dataset Status',
};

export function Header() {
  const location = useLocation();
  const [health, setHealth] = useState({ status: 'checking', database: 'checking' });
  const [alertSummary, setAlertSummary] = useState({ openAlerts: 0, criticalCount: 0 });

  const fetchStatus = async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);
    } catch {
      setHealth({ status: 'offline', database: 'disconnected' });
    }

    try {
      const overview = await api.getDashboardOverview();
      if (overview?.alerts_by_severity) {
        const crit = overview.alerts_by_severity.critical || 0;
        const high = overview.alerts_by_severity.high || 0;
        const med = overview.alerts_by_severity.medium || 0;
        const low = overview.alerts_by_severity.low || 0;
        setAlertSummary({
          openAlerts: crit + high + med + low,
          criticalCount: crit,
        });
      }
    } catch {
      // Non-blocking
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const pathParts = location.pathname.split('/').filter(Boolean);
  const isUserDetail = pathParts.length === 2 && pathParts[0] === 'users';
  const currentTitle = isUserDetail
    ? `User Dossier: ${pathParts[1]}`
    : ROUTE_LABELS[location.pathname] || 'Analytics';

  return (
    <header className="app-header">
      <div className="header-breadcrumbs">
        <Link to="/" className="breadcrumb-root" title="UEBA Sentinel Home">
          <Home size={14} />
          <span>UEBA</span>
        </Link>
        <ChevronRight size={12} className="breadcrumb-separator" />
        {isUserDetail ? (
          <>
            <Link to="/users" className="breadcrumb-link">
              Entities
            </Link>
            <ChevronRight size={12} className="breadcrumb-separator" />
            <span className="breadcrumb-current font-mono">{pathParts[1]}</span>
          </>
        ) : (
          <span className="breadcrumb-current">{currentTitle}</span>
        )}
      </div>

      <div className="header-actions">
        {/* Environment / System Health Pill */}
        <Link to="/system" className="health-indicator-pill" title="Backend API & Persistence Status">
          <span
            className={`health-dot ${
              health.status === 'ok' ? 'health-dot-ok' : 'health-dot-error'
            }`}
          />
          <span className="health-label font-mono">
            {health.status === 'ok' ? 'API 1.0 &bull; LIVE' : 'CONNECTING'}
          </span>
        </Link>

        {/* Real Alert Notification Indicator */}
        <Link
          to="/alerts"
          className="header-alerts-btn"
          aria-label={`Alert Queue: ${alertSummary.openAlerts} alerts`}
          title={`Total Alerts: ${alertSummary.openAlerts}`}
        >
          <Bell size={16} />
          {alertSummary.openAlerts > 0 && (
            <span
              className={`alerts-count-badge ${
                alertSummary.criticalCount > 0 ? 'badge-crit-pulse' : ''
              }`}
            >
              {alertSummary.openAlerts}
            </span>
          )}
        </Link>
      </div>
    </header>
  );
}
