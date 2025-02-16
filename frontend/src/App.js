// src/App.js
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import React from 'react';
import { faMicrophone, faCalendar, faCog, faChartBar } from '@fortawesome/free-solid-svg-icons';
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
          <li><Link to="/" title="Recording"><span><FontAwesomeIcon icon={faMicrophone} /></span></Link></li>
          <li><Link to="/calendar" title="Calendar"><span><FontAwesomeIcon icon={faCalendar} /></span></Link></li>
          <li><Link to="/reports" title="Reports"><span><FontAwesomeIcon icon={faChartBar} /></span></Link></li>
          <li><Link to="/settings" title="Settings"><span><FontAwesomeIcon icon={faCog} /></span></Link></li>
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

export { App };
export default App;
