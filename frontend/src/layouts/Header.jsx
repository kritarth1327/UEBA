import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Bell, ShieldCheck, AlertCircle, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import './Header.css';

const ROUTE_LABELS = {
  '/': 'Security Overview',
  '/users': 'User Directory',
  '/alerts': 'Alert Investigation Queue',
  '/models': 'Models & Evaluation Metrics',
  '/system': 'System & Data Status',
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

  // Determine breadcrumbs
  const pathParts = location.pathname.split('/').filter(Boolean);
  const isUserDetail = pathParts.length === 2 && pathParts[0] === 'users';
  const currentTitle = isUserDetail
    ? `User Investigation: ${pathParts[1]}`
    : ROUTE_LABELS[location.pathname] || 'Analytics';

  return (
    <header className="app-header">
      <div className="header-breadcrumbs">
        <Link to="/" className="breadcrumb-root">
          UEBA
        </Link>
        <span className="breadcrumb-separator">/</span>
        {isUserDetail ? (
          <>
            <Link to="/users" className="breadcrumb-link">
              Users
            </Link>
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-current font-mono">{pathParts[1]}</span>
          </>
        ) : (
          <span className="breadcrumb-current">{currentTitle}</span>
        )}
      </div>

      <div className="header-actions">
        {/* System Health Pill */}
        <Link to="/system" className="health-indicator-pill" title="Database & backend operational status">
          <span
            className={`health-dot ${
              health.status === 'ok' ? 'health-dot-ok' : 'health-dot-error'
            }`}
          />
          <span className="health-label">
            {health.status === 'ok' ? 'API Online' : 'Connecting...'}
          </span>
        </Link>

        {/* Real Alert Indicator */}
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
