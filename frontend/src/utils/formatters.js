export function formatDate(dateString) {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateTimeString) {
  if (!dateTimeString) return '—';
  try {
    const d = new Date(dateTimeString);
    if (isNaN(d.getTime())) return dateTimeString;
    return d.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return dateTimeString;
  }
}

export function formatRiskScore(score) {
  if (score === null || score === undefined) return 'Unavailable';
  return `${Number(score).toFixed(1)}`;
}

export function getRiskBadgeClass(level, score) {
  if (level) {
    const upper = level.toUpperCase();
    if (upper === 'CRITICAL') return 'badge-critical';
    if (upper === 'HIGH') return 'badge-high';
    if (upper === 'MEDIUM') return 'badge-medium';
    if (upper === 'LOW') return 'badge-low';
  }
  if (score !== null && score !== undefined) {
    if (score >= 90) return 'badge-critical';
    if (score >= 70) return 'badge-high';
    if (score >= 40) return 'badge-medium';
    return 'badge-low';
  }
  return 'badge-neutral';
}

export function getSeverityBadgeClass(severity) {
  if (!severity) return 'badge-neutral';
  const upper = severity.toUpperCase();
  if (upper === 'CRITICAL') return 'badge-critical';
  if (upper === 'HIGH') return 'badge-high';
  if (upper === 'MEDIUM') return 'badge-medium';
  if (upper === 'LOW') return 'badge-low';
  return 'badge-neutral';
}

export function getStatusBadgeClass(status) {
  if (!status) return 'badge-neutral';
  const upper = status.toUpperCase();
  if (upper === 'OPEN') return 'badge-high';
  if (upper === 'INVESTIGATING') return 'badge-medium';
  if (upper === 'RESOLVED') return 'badge-low';
  if (upper === 'DISMISSED') return 'badge-neutral';
  return 'badge-neutral';
}
