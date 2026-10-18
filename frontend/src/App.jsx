import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './layouts/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { UsersPage } from './pages/UsersPage';
import { UserInvestigationPage } from './pages/UserInvestigationPage';
import { AlertsPage } from './pages/AlertsPage';
import { ModelsPage } from './pages/ModelsPage';
import { SystemPage } from './pages/SystemPage';
import { EmptyState } from './components/EmptyState';
import { AlertCircle } from 'lucide-react';

function NotFoundPage() {
  return (
    <div style={{ padding: '32px 0' }}>
      <EmptyState
        icon={AlertCircle}
        title="Page Not Found"
        description="The requested route does not exist."
        actionLabel="Back to Dashboard"
        onAction={() => (window.location.href = '/')}
      />
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="users/:userId" element={<UserInvestigationPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="system" element={<SystemPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
