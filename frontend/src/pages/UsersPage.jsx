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
  const debouncedSearch = useDebounce(searchInput, 300);

  const [department, setDepartment] = useState(initialDept);
  const [sortBy, setSortBy] = useState(initialSortBy);
  const [sortDir, setSortDir] = useState(initialSortDir);
  const [page, setPage] = useState(initialPage);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Sync to URL search params
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
      setError(err.message || 'Failed to retrieve user records.');
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
      <div className="users-header">
        <div>
          <h1 className="users-title">User Directory & Entity Monitoring</h1>
          <p className="users-subtitle">
            Searchable employee profiles with real-time risk assessments and historical activity.
          </p>
        </div>

        <div className="users-count-tag">
          <UsersIcon size={14} />
          <span>{data?.total ?? 0} Ingested Entities</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="users-filter-bar card">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search by User ID, name, email, or role..."
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              setPage(1);
            }}
          />
        </div>

        <div className="filter-controls">
          <div className="select-wrapper">
            <Building2 size={14} className="select-icon" />
            <select
              className="filter-select"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All Departments</option>
              <option value="Engineering">Engineering</option>
              <option value="Finance">Finance</option>
              <option value="HR">Human Resources</option>
              <option value="IT">Information Technology</option>
              <option value="Sales">Sales & Marketing</option>
              <option value="Legal">Legal</option>
            </select>
          </div>

          <div className="select-wrapper">
            <ArrowUpDown size={14} className="select-icon" />
            <select
              className="filter-select"
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
              <option value="alerts-desc">Alerts (Most First)</option>
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
        <LoadingSpinner message="Querying user directory..." />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={UsersIcon}
          title={searchInput || department ? 'No Matching Users Found' : 'User Directory Empty'}
          description={
            searchInput || department
              ? 'No users match your search query or department filter.'
              : 'No enterprise users have been ingested yet. The CERT dataset r4.2 is awaiting download and pipeline processing.'
          }
          actionLabel={searchInput || department ? 'Clear Filters' : 'Check Ingestion Status'}
          onAction={searchInput || department ? clearFilters : () => navigate('/system')}
        />
      ) : (
        <div className="card users-table-card">
          <div className="table-responsive">
            <table className="users-table">
              <thead>
                <tr>
                  <th onClick={() => handleSort('user_id')} className="sortable-th">
                    <span>User Identifier</span>
                    <ArrowUpDown size={12} />
                  </th>
                  <th>Employee Name</th>
                  <th onClick={() => handleSort('department')} className="sortable-th">
                    <span>Department</span>
                    <ArrowUpDown size={12} />
                  </th>
                  <th>Role</th>
                  <th onClick={() => handleSort('risk')} className="sortable-th">
                    <span>Hybrid Risk</span>
                    <ArrowUpDown size={12} />
                  </th>
                  <th>Risk Level</th>
                  <th>Last Assessment</th>
                  <th onClick={() => handleSort('alerts')} className="sortable-th">
                    <span>Alerts</span>
                    <ArrowUpDown size={12} />
                  </th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((user) => (
                  <tr
                    key={user.user_id}
                    className="clickable-row"
                    onClick={() => navigate(`/users/${user.user_id}`)}
                  >
                    <td className="font-mono font-bold">{user.user_id}</td>
                    <td>{user.employee_name || '—'}</td>
                    <td>{user.department || '—'}</td>
                    <td className="text-muted">{user.role || '—'}</td>
                    <td className="font-mono">
                      {formatRiskScore(user.latest_risk_score)}
                    </td>
                    <td>
                      <span className={`badge ${getRiskBadgeClass(user.latest_risk_level)}`}>
                        {user.latest_risk_level || 'UNASSESSED'}
                      </span>
                    </td>
                    <td className="text-muted">{formatDate(user.latest_assessment_date)}</td>
                    <td className="font-mono">{user.alert_count}</td>
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
            <div className="pagination-footer">
              <span className="pagination-info text-muted">
                Page {data.page} of {data.total_pages} ({data.total} total users)
              </span>
              <div className="pagination-buttons">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={14} />
                  <span>Previous</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={page >= data.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <span>Next</span>
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
