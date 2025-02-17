// src/CalendarPage.js
import React, { useState, useEffect, useMemo } from 'react';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import './CalendarPage.css';
import axios from 'axios';

const CalendarPage = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [activityLogs, setActivityLogs] = useState([]);
  const [sortColumn, setSortColumn] = useState('timestamp');
  const [sortDirection, setSortDirection] = useState('desc');

  useEffect(() => {
    fetchLogsForDate(selectedDate);
  }, [selectedDate]);

  const fetchLogsForDate = async (date) => {
    try {
      // Format the date using toLocaleDateString with 'en-CA' for YYYY-MM-DD format in local time.
      const formattedDate = date.toLocaleDateString('en-CA');
      console.log("Fetching logs for date:", formattedDate);
      const response = await axios.get('http://localhost:8000/api/activity-logs', {
        params: { date: formattedDate }
      });
      console.log("Fetched logs:", response.data);
      setActivityLogs(response.data);
    } catch (error) {
      console.error("Error fetching activity logs:", error);
    }
  };

  const sortedLogs = useMemo(() => {
    const logsCopy = [...activityLogs];
    logsCopy.sort((a, b) => {
      let valA = a[sortColumn];
      let valB = b[sortColumn];
      if (sortColumn === 'timestamp') {
        valA = new Date(valA);
        valB = new Date(valB);
      }
      if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
      if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
    return logsCopy;
  }, [activityLogs, sortColumn, sortDirection]);

  const handleHeaderClick = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1>Activity-Logs</h1>
      <Calendar onChange={setSelectedDate} value={selectedDate} />
      <h2>Activity Logs for {selectedDate.toLocaleDateString()}</h2>
      {sortedLogs.length > 0 ? (
        <table className="log-table">
          <thead>
            <tr>
              <th onClick={() => handleHeaderClick('timestamp')}>
                Timestamp
              </th>
              <th onClick={() => handleHeaderClick('category')}>
              Category
              </th>
              <th onClick={() => handleHeaderClick('group')}>
                Group
              </th>
              <th onClick={() => handleHeaderClick('duration_minutes')}>
                Duration
              </th>
              <th onClick={() => handleHeaderClick('description')}>
                Description
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedLogs.map((log) => (
              <tr key={log.id}>
                <td>{new Date(log.timestamp).toLocaleString()}</td>
                <td>{log.category}</td>
                <td>{log.group}</td>
                <td>{log.duration_minutes}</td>
                <td>{log.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No activity logs found for this date.</p>
      )}
    </div>
  );
};

export default CalendarPage;
