import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import ReactMarkdown from 'react-markdown';
import './ReportsPage.css';

const ReportsPage = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchReport(selectedDate.toLocaleDateString('en-CA'));
  }, [selectedDate]);

  const fetchReport = async (dateValue) => {
    setLoading(true);
    setError(null);
    try {
      console.log("Fetching report for date:", dateValue);
      const response = await axios.get('http://localhost:8000/api/reports/daily-report', {
        params: { date: dateValue }
      });
      console.log("Raw response data:", response.data);
      
      // Debug: log the keys of the report object received
      if (response.data.report) {
        console.log("Report keys:", Object.keys(response.data.report));
      } else {
        console.log("Response data (no report key):", response.data);
      }

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

  const handleDateChange = (newDate) => {
    setSelectedDate(newDate);
    fetchReport(newDate.toLocaleDateString('en-CA'));
  };

  const handleForceGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post('http://localhost:8000/api/reports/force-daily-report', null, {
        params: { date: selectedDate.toLocaleDateString('en-CA') }
      });
      console.log("Force generate response:", response.data);
      if (response.data.report) {
        setReport(response.data.report);
      } else {
        await fetchReport(selectedDate.toLocaleDateString('en-CA'));
      }
    } catch (error) {
      console.error("Error forcing report generation:", error);
      setError(error.message);
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  // Debug: log the current report object before rendering
  useEffect(() => {
    if (report) {
      console.log("Current report object:", report);
    }
  }, [report]);

  return (
    <div className="reports-page" style={{ padding: '20px' }}>
      <h1>Daily Report</h1>
      
      <div className="controls" style={{ marginBottom: '20px' }}>
        <label>
          Report Date:{' '}
          <Calendar onChange={handleDateChange} value={selectedDate} />
        </label>
        <button 
          onClick={() => fetchReport(selectedDate.toLocaleDateString('en-CA'))} 
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
            {report.executive_summary ? (
              <>
                <p>
                  <strong>Total Time:</strong> {report.executive_summary.total_time} minutes
                </p>
                {report.executive_summary.summary && (
                  <div className="time-by-category-group">
                    <h3>Time by Category/Group</h3>
                    <ul>
                      {Object.entries(report.executive_summary.summary).map(([category, groups]) => (
                        <div key={category}>
                          <h4>{category}</h4>
                          <ul>
                            {Object.entries(groups).map(([group, minutes]) => (
                              <li key={group}>{group}: {minutes} minutes</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </ul>
                  </div>
                )}
                {report.executive_summary.progress_report && (
                  <div className="progress-report">
                    <h3>Progress</h3>
                    <p>{report.executive_summary.progress_report}</p>
                  </div>
                )}
              </>
            ) : (
              <p>Executive summary not available.</p>
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
          
          <div className="markdown-report">
            <h2>Markdown Report</h2>
            <ReactMarkdown>{report.markdown_report}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
