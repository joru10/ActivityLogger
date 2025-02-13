// src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Recorder from './Recorder';
import CalendarPage from './CalendarPage';
import SettingsPage from './SettingsPage';
import ReportsPage from './ReportsPage';
import NotificationManager from './NotificationManager';

function AppContent() {
  return (
    <div>
      <NotificationManager /> {/* Include the notification manager */}
      <nav style={{ padding: '10px', backgroundColor: '#eee' }}>
        <ul style={{ listStyle: 'none', display: 'flex', gap: '20px', margin: 0, padding: 0 }}>
          <li><Link to="/">Recording</Link></li>
          <li><Link to="/calendar">Calendar</Link></li>
          <li><Link to="/settings">Settings</Link></li>
          <li><Link to="/reports">Reports</Link></li>
        </ul>
      </nav>
      <Routes>
        <Route path="/" element={<Recorder />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;