import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search,
  Filter,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Shield,
  Building2,
  Users as UsersIcon,
  X,
  ExternalLink,
} from 'lucide-react';
import { api } from '../api/client';
import { useDebounce } from '../hooks/useDebounce';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import {
  formatDate,
  formatRiskScore,
  getRiskBadgeClass,
} from '../utils/formatters';
import './UsersPage.css';

export function UsersPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialSearch = searchParams.get('search') || '';
  const initialDept = searchParams.get('department') || '';
  const initialSortBy = searchParams.get('sort_by') || 'user_id';
  const initialSortDir = searchParams.get('sort_dir') || 'asc';
  const initialPage = parseInt(searchParams.get('page') || '1', 10);

  const [searchInput, setSearchInput] = useState(initialSearch);
  const debouncedSearch = useDebounce(searchInput, 280);

  const [department, setDepartment] = useState(initialDept);
  const [sortBy, setSortBy] = useState(initialSortBy);
  const [sortDir, setSortDir] = useState(initialSortDir);
  const [page, setPage] = useState(initialPage);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Sync state to URL search parameters
  useEffect(() => {
    const params = new URLSearchParams();
    if (debouncedSearch) params.set('search', debouncedSearch);
    if (department) params.set('department', department);
    if (sortBy !== 'user_id') params.set('sort_by', sortBy);
    if (sortDir !== 'asc') params.set('sort_dir', sortDir);
    if (page > 1) params.set('page', page.toString());
    setSearchParams(params, { replace: true });
  }, [debouncedSearch, department, sortBy, sortDir, page, setSearchParams]);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getUsers({
        page,
        page_size: 15,
        search: debouncedSearch || undefined,
        department: department || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to retrieve entity records.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [debouncedSearch, department, sortBy, sortDir, page]);

  const handleSort = (column) => {
    if (sortBy === column) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
    setPage(1);
  };

  const clearFilters = () => {
    setSearchInput('');
    setDepartment('');
    setSortBy('user_id');
    setSortDir('asc');
    setPage(1);
  };

  return (
    <div className="users-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Entity Intelligence & User Directory</h1>
          <p className="page-subtitle">
            Monitored employees and service accounts with behavior baseline profiles and risk assessments.
          </p>
        </div>

        <div className="users-count-tag font-mono">
          <UsersIcon size={14} className="text-teal" />
          <span>{data?.total ?? 0} Ingested Entities</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card users-filter-bar">
        <div className="search-box">
          <Search size={15} className="search-icon text-muted" />
          <input
            type="text"
            className="search-field"
            placeholder="Search by User ID, name, email, or role..."
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              setPage(1);
            }}
          />
          {searchInput && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={() => {
                setSearchInput('');
                setPage(1);
              }}
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div className="filter-dropdowns">
          <div className="select-container">
            <Building2 size={14} className="select-icon text-muted" />
            <select
              className="styled-select"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All Departments</option>
              <option value="Engineering">Engineering</option>
              <option value="Finance">Finance</option>
              <option value="Human Resources">Human Resources</option>
              <option value="IT">Information Technology</option>
              <option value="Sales">Sales & Marketing</option>
              <option value="Legal">Legal</option>
            </select>
          </div>

          <div className="select-container">
            <ArrowUpDown size={14} className="select-icon text-muted" />
            <select
              className="styled-select"
              value={`${sortBy}-${sortDir}`}
              onChange={(e) => {
                const [sb, sd] = e.target.value.split('-');
                setSortBy(sb);
                setSortDir(sd);
                setPage(1);
              }}
            >
              <option value="user_id-asc">User ID (A-Z)</option>
              <option value="user_id-desc">User ID (Z-A)</option>
              <option value="risk-desc">Risk Score (Highest First)</option>
              <option value="risk-asc">Risk Score (Lowest First)</option>
              <option value="alerts-desc">Alerts Count (Most First)</option>
            </select>
          </div>

          {(searchInput || department) && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={clearFilters}>
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={fetchUsers} />}

      {loading ? (
        <LoadingSpinner message="Querying enterprise directory..." />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={UsersIcon}
          title={searchInput || department ? 'No Matching Entities Found' : 'User Directory Empty'}
          description={
            searchInput || department
              ? 'No entities match your search term or department filter.'
              : 'No enterprise users have been ingested yet. Place a supported dataset in the configured raw-data directory and run the ingestion pipeline.'
          }
          actionLabel={searchInput || department ? 'Clear Filters' : 'Check Ingestion Status'}
          onAction={searchInput || department ? clearFilters : () => navigate('/system')}
        />
      ) : (
        <div className="card users-table-card">
          <div className="table-responsive">
            <table className="compact-table">
              <thead>
                <tr>
                  <th onClick={() => handleSort('user_id')} className="sortable-th">
                    <span>Entity ID</span>
                    <ArrowUpDown size={11} />
                  </th>
                  <th>Employee Name</th>
                  <th onClick={() => handleSort('department')} className="sortable-th">
                    <span>Department</span>
                    <ArrowUpDown size={11} />
                  </th>
                  <th>Role</th>
                  <th onClick={() => handleSort('risk')} className="sortable-th">
                    <span>Hybrid Risk</span>
                    <ArrowUpDown size={11} />
                  </th>
                  <th>Classification</th>
                  <th>Last Assessment</th>
                  <th onClick={() => handleSort('alerts')} className="sortable-th">
                    <span>Alerts</span>
                    <ArrowUpDown size={11} />
                  </th>
                  <th>Investigation</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((user) => (
                  <tr
                    key={user.user_id}
                    className="clickable-row"
                    onClick={() => navigate(`/users/${user.user_id}`)}
                  >
                    <td className="font-mono font-bold text-primary">{user.user_id}</td>
                    <td className="font-medium text-primary">{user.employee_name || '—'}</td>
                    <td>{user.department || '—'}</td>
                    <td className="text-muted">{user.role || '—'}</td>
                    <td className="font-mono font-bold">
                      {user.latest_assessment_date
                        ? formatRiskScore(user.latest_risk_score)
                        : 'Unassessed'}
                    </td>
                    <td>
                      <span className={`badge ${getRiskBadgeClass(user.latest_risk_level)}`}>
                        {user.latest_risk_level || 'UNASSESSED'}
                      </span>
                    </td>
                    <td className="text-muted">{formatDate(user.latest_assessment_date)}</td>
                    <td className="font-mono font-semibold">{user.alert_count}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/users/${user.user_id}`);
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

          {/* Pagination Controls */}
          {data.total_pages > 1 && (
            <div className="pagination-bar">
              <span className="pagination-text text-muted font-mono">
                Showing {((data.page - 1) * data.page_size) + 1} &ndash; {Math.min(data.page * data.page_size, data.total)} of {data.total} entities
              </span>
              <div className="pagination-controls">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={13} />
                  <span>Previous</span>
                </button>
                <span className="page-indicator font-mono">
                  {data.page} / {data.total_pages}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= data.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <span>Next</span>
                  <ChevronRight size={13} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
