import React, { useState, useEffect } from 'react';
import axios from 'axios';

const ActivityLogsTable = () => {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        // Fetch all logs without a date filter
        const response = await axios.get('http://localhost:8000/api/activity-logs');
        console.log("Fetched logs:", response.data);
        
        // Sort logs by timestamp descending (newest first)
        const sortedLogs = response.data.sort(
          (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
        );
        setLogs(sortedLogs);
      } catch (error) {
        console.error("Error fetching activity logs:", error);
      }
    };

    fetchLogs();
  }, []);

  return (
    <div style={{ padding: '20px' }}>
      <h2>Activity Logs</h2>
      <table border="1" cellPadding="8" cellSpacing="0">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Group</th>
            <th>Duration (min)</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {logs.length > 0 ? (
            logs.map((log) => (
              <tr key={log.id}>
                <td>{new Date(log.timestamp).toLocaleString()}</td>
                <td>{log.group}</td>
                <td>{log.duration_minutes}</td>
                <td>{log.description}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="4">No activity logs found.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default ActivityLogsTable;