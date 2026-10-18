import React from 'react';
import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Users,
  ShieldAlert,
  Cpu,
  Activity,
  ChevronLeft,
  ChevronRight,
  Shield,
  FileSearch,
} from 'lucide-react';
import './Sidebar.css';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/users', label: 'Entities & Users', icon: Users },
  { path: '/alerts', label: 'Alert Queue', icon: ShieldAlert },
  { path: '/models', label: 'Models & Evaluation', icon: Cpu },
  { path: '/system', label: 'System & Ingestion', icon: Activity },
];

export function Sidebar({ collapsed, onToggle }) {
  return (
    <motion.aside
      className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}
      animate={{ width: collapsed ? 68 : 240 }}
      transition={{ duration: 0.18, ease: 'easeInOut' }}
    >
      <div className="sidebar-brand">
        <div className="brand-icon-wrapper">
          <Shield size={19} className="brand-icon" />
        </div>
        {!collapsed && (
          <div className="brand-text">
            <span className="brand-name">UEBA Sentinel</span>
            <span className="brand-tag">Insider Threat Intelligence</span>
          </div>
        )}
      </div>

      <div className="sidebar-section-label">
        {!collapsed && <span>OPERATIONS</span>}
      </div>

      <nav className="sidebar-nav" aria-label="Main Navigation">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-link ${isActive ? 'nav-link-active' : ''}`
              }
              title={collapsed ? item.label : undefined}
            >
              <Icon size={17} className="nav-icon" />
              {!collapsed && <span className="nav-label">{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <button
          type="button"
          className="collapse-toggle-btn"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
          {!collapsed && <span>Collapse Sidebar</span>}
        </button>
      </div>
    </motion.aside>
  );
}
