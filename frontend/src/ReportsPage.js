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
  const [reportType, setReportType] = useState('daily'); // 'daily', 'weekly', 'monthly', 'quarterly', 'annual'

  useEffect(() => {
    fetchReport(selectedDate.toLocaleDateString('en-CA'));
  }, [selectedDate, reportType]);

  const fetchReport = async (dateValue) => {
    setLoading(true);
    setError(null);
    try {
      console.log(`Fetching ${reportType} report for date:`, dateValue);
      
      let endpoint = 'daily-report';
      if (reportType !== 'daily') {
        endpoint = `${reportType}-report`;
      }
      
      const response = await axios.get(`http://localhost:8000/api/reports/${endpoint}`, {
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
        setError(`No ${reportType} report found for this date`);
        setReport(null);
      } else if (response.data.report) {
        setReport(response.data.report);
      } else {
        // Directly handle the response data
        console.log("Setting report directly from response data");
        // Check if this is a weekly report with html_report
        if (reportType === 'weekly' && response.data.html_report) {
          console.log("Weekly report with html_report detected");
        }
        setReport(response.data);
      }
    } catch (error) {
      console.error(`Error fetching ${reportType} report:`, error);
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
      // For daily reports, use the existing endpoint
      if (reportType === 'daily') {
        const response = await axios.post('http://localhost:8000/api/reports/force-daily-report', null, {
          params: { date: selectedDate.toLocaleDateString('en-CA') }
        });
        console.log("Force generate response:", response.data);
        if (response.data.report) {
          setReport(response.data.report);
        } else {
          await fetchReport(selectedDate.toLocaleDateString('en-CA'));
        }
      } else {
        // For other report types, use the scheduler trigger endpoint
        const response = await axios.post(`http://localhost:8000/api/scheduler/trigger/${reportType}`);
        console.log(`Force generate ${reportType} report response:`, response.data);
        if (response.data.success) {
          setError(`${reportType.charAt(0).toUpperCase() + reportType.slice(1)} report generation triggered. It may take a moment to complete.`);
          // Wait a bit before fetching the report
          setTimeout(() => fetchReport(selectedDate.toLocaleDateString('en-CA')), 3000);
        } else {
          setError(response.data.error || `Failed to generate ${reportType} report`);
        }
      }
    } catch (error) {
      console.error(`Error forcing ${reportType} report generation:`, error);
      setError(error.message);
      setReport(null);
    } finally {
      setLoading(false);
    }
  };
  
  const handleExportCSV = async () => {
    try {
      const dateParam = reportType === 'daily' ? `?date=${selectedDate.toLocaleDateString('en-CA')}` : '';
      const url = `http://localhost:8000/api/reports/export-csv/${reportType}${dateParam}`;
      
      // Create a temporary link element to trigger the download
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${reportType}_report.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error(`Error exporting ${reportType} report as CSV:`, error);
      setError(`Failed to export ${reportType} report as CSV: ${error.message}`);
    }
  };

  // Debug: log the current report object before rendering
  useEffect(() => {
    if (report) {
      console.log("Current report object:", report);
      console.log("Report has html_report?", Boolean(report.html_report));
      console.log("Report has markdown_report?", Boolean(report.markdown_report));
      if (report.html_report) {
        console.log("HTML report length:", report.html_report.length);
      }
    }
  }, [report]);

  return (
    <div className="reports-page" style={{ padding: '20px' }}>
      <h1>{reportType.charAt(0).toUpperCase() + reportType.slice(1)} Report</h1>
      
      <div className="report-type-selector" style={{ marginBottom: '20px' }}>
        <div className="tabs" style={{ display: 'flex', borderBottom: '1px solid #ccc', marginBottom: '15px' }}>
          {['daily', 'weekly', 'monthly', 'quarterly', 'annual'].map(type => (
            <button 
              key={type}
              onClick={() => setReportType(type)}
              style={{
                padding: '10px 15px',
                border: 'none',
                background: reportType === type ? '#f0f0f0' : 'transparent',
                borderBottom: reportType === type ? '2px solid #007bff' : 'none',
                fontWeight: reportType === type ? 'bold' : 'normal',
                cursor: 'pointer'
              }}
            >
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </button>
          ))}
        </div>
      </div>
      
      <div className="controls" style={{ marginBottom: '20px' }}>
        <label>
          Report Date:{' '}
          <Calendar onChange={handleDateChange} value={selectedDate} />
        </label>
        <div style={{ marginTop: '10px' }}>
          <button 
            onClick={() => fetchReport(selectedDate.toLocaleDateString('en-CA'))} 
            style={{ marginRight: '10px' }}
            disabled={loading}
          >
            Refresh Report
          </button>
          <button 
            onClick={handleForceGenerate}
            style={{ marginRight: '10px' }}
            disabled={loading}
          >
            Force Generate Report
          </button>
          <button 
            onClick={handleExportCSV}
            style={{ marginRight: '10px' }}
            disabled={loading || !report}
          >
            Export as CSV
          </button>
        </div>
      </div>
      
      {loading && <p>Loading report...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      
      {!loading && !error && report && (
        <div className="report-content">
          {/* Debug info */}
          <div style={{ display: 'none' }}>
            <p>Debug: Report keys: {Object.keys(report).join(', ')}</p>
            <p>Has html_report: {String(Boolean(report.html_report))}</p>
          </div>
          
          {report.html_report && report.html_report.length > 0 ? (
            <div className="html-report">
              <iframe 
                srcDoc={report.html_report}
                className="html-report-content"
                style={{ width: '100%', height: '800px', border: 'none' }}
                title={`${reportType.charAt(0).toUpperCase() + reportType.slice(1)} Report`}
                sandbox="allow-scripts"
              />
            </div>
          ) : report.markdown_report ? (
            <div className="markdown-report">
              <ReactMarkdown>{report.markdown_report}</ReactMarkdown>
              
              {report.executive_summary && (
                <div className="executive-summary">
                  <h2>Executive Summary</h2>
                  <p><strong>Total Time:</strong> {report.executive_summary.total_time} minutes</p>
                  
                  {report.executive_summary.time_by_group && (
                    <div>
                      <h3>Time by Group</h3>
                      <ul>
                        {Object.entries(report.executive_summary.time_by_group).map(([group, time]) => (
                          <li key={group}><strong>{group}:</strong> {time} minutes</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {report.executive_summary.time_by_category && (
                    <div>
                      <h3>Time by Category</h3>
                      <ul>
                        {Object.entries(report.executive_summary.time_by_category).map(([category, time]) => (
                          <li key={category}><strong>{category}:</strong> {time} minutes</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              
              {report.details && report.details.length > 0 && (
                <div className="details">
                  <h2>Activity Details</h2>
                  <table className="activity-table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Group</th>
                        <th>Category</th>
                        <th>Duration</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.details.map((activity, index) => (
                        <tr key={index}>
                          <td>{new Date(activity.timestamp).toLocaleTimeString()}</td>
                          <td>{activity.group}</td>
                          <td>{activity.category}</td>
                          <td>{activity.duration_minutes} min</td>
                          <td>{activity.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="no-report-content">
              <p>No report content available. Try generating a report first.</p>
              {/* If we have a report object but no html_report or markdown_report, show what we do have */}
              {Object.keys(report).length > 0 && (
                <div className="debug-report-info">
                  <p><strong>Available report data:</strong></p>
                  <pre>{JSON.stringify(report, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
