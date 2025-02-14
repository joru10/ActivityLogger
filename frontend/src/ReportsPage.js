import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './ReportsPage.css';

const ReportsPage = () => {
  const [dateStr, setDateStr] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const today = new Date();
    const formatted = today.toISOString().split('T')[0];
    setDateStr(formatted);
    fetchReport(formatted);
  }, []);

  const fetchReport = async (dateValue) => {
    setLoading(true);
    setError(null);
    try {
      console.log("Fetching report for date:", dateValue);
      const response = await axios.get('http://localhost:8000/api/reports/daily-report', {
        params: { date: dateValue }
      });
      
      if (response.data.error) {
        setError(response.data.error);
        setReport(null);
      } else if (response.data.message?.includes("No report")) {
        setError("No report found for this date");
        setReport(null);
      } else if (response.data.report) {
        setReport(response.data.report);
      } else {
        setReport(response.data);
      }
    } catch (error) {
      console.error("Error fetching report:", error);
      setError(error.message);
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  const handleDateChange = (event) => {
    const newDate = event.target.value;
    setDateStr(newDate);
    fetchReport(newDate);
  };

  const handleForceGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post('http://localhost:8000/api/reports/force-daily-report', null, {
        params: { date: dateStr }
      });       
      if (response.data.report) {
        setReport(response.data.report);
      } else {
        await fetchReport(dateStr);
      }
    } catch (error) {
      console.error("Error forcing report generation:", error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="reports-page" style={{ padding: '20px' }}>
      <h1>Daily Report</h1>
      
      <div className="controls" style={{ marginBottom: '20px' }}>
        <label>
          Report Date:{' '}
          <input 
            type="date" 
            value={dateStr} 
            onChange={handleDateChange} 
            style={{ marginLeft: '10px' }} 
          />
        </label>
        <button 
          onClick={() => fetchReport(dateStr)} 
          style={{ marginLeft: '10px' }}
          disabled={loading}
        >
          Refresh Report
        </button>
        <button 
          onClick={handleForceGenerate} 
          style={{ marginLeft: '10px' }}
          disabled={loading}
        >
          Force Generate Report
        </button>
      </div>
      
      {loading && <p>Loading report...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      
      {!loading && !error && report && (
        <div className="report-content">
          <div className="executive-summary">
            <h2>Executive Summary</h2>
            <p><strong>Total Time:</strong> {report.executive_summary?.total_time} minutes</p>
            {report.executive_summary?.time_by_group && (
              <div className="time-by-group">
                <h3>Time by Group</h3>
                <ul>
                  {Object.entries(report.executive_summary.time_by_group).map(([group, minutes]) => (
                    <li key={group}>{group}: {minutes} minutes</li>
                  ))}
                </ul>
              </div>
            )}
            {report.executive_summary?.progress_report && (
              <div className="progress-report">
                <h3>Progress</h3>
                <p>{report.executive_summary.progress_report}</p>
              </div>
            )}
          </div>

          <div className="details">
            <h2>Details</h2>
            {report.details?.length > 0 ? (
              <ul>
                {report.details.map((activity, index) => (
                  <li key={`activity-${index}`}>
                    <strong>Category:</strong> {activity.category || 'others'}{' | '}
                    <strong>Group:</strong> {activity.group}{' | '}
                    <strong>Description:</strong> {activity.description}{' | '}
                    <strong>Timestamp:</strong> {activity.timestamp}{' | '}
                    <strong>Duration:</strong> {activity.duration_minutes} minutes
                  </li>
                ))}
              </ul>
            ) : (
              <p>No details available.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;