// src/ReportsPage.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const ReportsPage = () => {
  const [dateStr, setDateStr] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  // On component mount, set default date and fetch report.
  useEffect(() => {
    const today = new Date();
    // Use 'en-CA' to ensure the date is formatted as YYYY-MM-DD.
    const formatted = today.toLocaleDateString('en-CA');
    setDateStr(formatted);
    fetchReport(formatted);
  }, []);

  useEffect(() => {
    console.log("Fetching report for date:", dateStr);
  }, [dateStr]);

  const fetchReport = async (dateValue) => {
    setLoading(true);
    try {
      const response = await axios.get('http://localhost:8000/api/daily-report', {
        params: { date: dateValue }
      });
      console.log("Fetched report:", response.data);
      setReport(response.data);
    } catch (error) {
      console.error("Error fetching report:", error);
      setReport(null);
    }
    setLoading(false);
  };

  const handleDateChange = (e) => {
    setDateStr(e.target.value);
  };

  const handleFetchClick = () => {
    if (dateStr) {
      fetchReport(dateStr);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1>Daily Report</h1>
      <div style={{ marginBottom: '20px' }}>
        <label>
          Report Date (YYYY-MM-DD):{' '}
          <input 
            type="date" 
            value={dateStr} 
            onChange={handleDateChange} 
            style={{ marginLeft: '10px' }} 
          />
        </label>
        <button onClick={handleFetchClick} style={{ marginLeft: '10px' }}>
          Fetch Report
        </button>
      </div>
      {loading ? (
        <p>Loading report...</p>
      ) : report && report.executive_summary ? (
        <div>
          <h2>Executive Summary</h2>
          <pre>{JSON.stringify(report.executive_summary, null, 2)}</pre>
          {report.details && report.details.length > 0 && (
            <>
              <h3>Details</h3>
              <pre>{JSON.stringify(report.details, null, 2)}</pre>
            </>
          )}
          {report.raw_data && (
            <>
              <h3>Raw Data</h3>
              <pre>{JSON.stringify(report.raw_data, null, 2)}</pre>
            </>
          )}
        </div>
      ) : (
        <p>No report available for this date.</p>
      )}
    </div>
  );
};

export default ReportsPage;