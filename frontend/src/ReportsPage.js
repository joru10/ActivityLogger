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
  const [availableReports, setAvailableReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [showDebugInfo, setShowDebugInfo] = useState(true);

  // Helper function to get values from potentially nested report structure
  const getReportValue = (reportObj, key) => {
    if (!reportObj) return null;
    
    // Check if the value exists directly in the report object
    if (reportObj[key] !== undefined) {
      return reportObj[key];
    }
    
    // Check if the value exists in a nested report.report structure
    if (reportObj.report && reportObj.report[key] !== undefined) {
      return reportObj.report[key];
    }
    
    return null;
  };

  // Helper function to get executive summary from potentially nested report structure
  const getExecutiveSummary = (reportObj) => {
    if (!reportObj) return null;
    
    if (reportObj.executive_summary) {
      return reportObj.executive_summary;
    }
    
    if (reportObj.report && reportObj.report.executive_summary) {
      return reportObj.report.executive_summary;
    }
    
    return null;
  };

  useEffect(() => {
    // Fetch available reports when report type changes
    fetchAvailableReports();
    // Also fetch the report for the selected date
    fetchReport(selectedDate.toLocaleDateString('en-CA'));
  }, [selectedDate, reportType]);

  // Function to toggle debug info
  const toggleDebugInfo = () => {
    setShowDebugInfo(!showDebugInfo);
    console.log('Debug info toggled:', !showDebugInfo);
  };
  
  // Fetch the list of available reports for the current report type
  const fetchAvailableReports = async () => {
    try {
      console.log(`Attempting to fetch ${reportType} reports from http://localhost:8000/api/reports/list-reports/${reportType}`);
      const response = await axios.get(`http://localhost:8000/api/reports/list-reports/${reportType}`, {
        // Add cache-busting parameter to prevent browser caching
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' },
        params: { _t: new Date().getTime() } // Add timestamp to prevent caching
      });
      console.log(`Available ${reportType} reports:`, response.data);
      
      // Get all reports first
      const allReports = response.data.reports || [];
      
      // Log all available reports for debugging
      console.log('All available reports:', allReports.map(r => r.filename));
      
      // Always show all available reports
      console.log('Setting all available reports:', allReports.map(r => r.filename));
      setAvailableReports(allReports);
      
      // Try to find a report that matches the selected date
      if (selectedDate) {
        const selectedDateStr = selectedDate.toLocaleDateString('en-CA'); // YYYY-MM-DD
        console.log('Looking for report matching date:', selectedDateStr);
        
        let matchingReport = null;
        
        if (reportType === 'daily') {
          // For daily reports, look for exact date match in filename
          matchingReport = allReports.find(report => report.filename.includes(selectedDateStr));
          console.log('Matching daily report found:', matchingReport ? matchingReport.filename : 'none');
        } else if (reportType === 'weekly') {
          // For weekly reports, calculate the start of the week
          const dayOfWeek = selectedDate.getDay(); // 0 = Sunday, 1 = Monday, ...
          const daysSinceMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Adjust for Monday as first day
          const startOfWeek = new Date(selectedDate);
          startOfWeek.setDate(selectedDate.getDate() - daysSinceMonday);
          const startOfWeekStr = startOfWeek.toLocaleDateString('en-CA');
          
          console.log('Looking for weekly report starting on:', startOfWeekStr);
          
          // Try to find a report that matches the start of the week
          matchingReport = allReports.find(report => {
            if (report.date_range) {
              const reportStartDate = report.date_range.split(' to ')[0];
              return reportStartDate === startOfWeekStr;
            }
            return report.filename.includes(startOfWeekStr);
          });
          console.log('Matching weekly report found:', matchingReport ? matchingReport.filename : 'none');
        }
        
        if (matchingReport) {
          console.log('Setting selected report to matching report:', matchingReport.filename);
          setSelectedReport(matchingReport);
        } else {
          // If no matching report is found, we'll still show all available reports
          // but we won't automatically select one
          console.log('No matching report found for selected date, but showing all available reports');
          // Don't clear the selection if we already have one
          if (!selectedReport && allReports.length > 0) {
            console.log('No current selection, setting to first available report');
            setSelectedReport(allReports[0]);
          }
        }
      } else {
        // If no date is selected but reports are available, select the first one
        if (allReports.length > 0) {
          console.log('No date selected, setting first report:', allReports[0].filename);
          setSelectedReport(allReports[0]);
        } else {
          setSelectedReport(null);
        }
      }
      
      // We're now showing all reports instead of filtering them
    } catch (error) {
      console.error(`Error fetching available ${reportType} reports:`, error);
      if (error.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        console.error('Error response data:', error.response.data);
        console.error('Error response status:', error.response.status);
        console.error('Error response headers:', error.response.headers);
      } else if (error.request) {
        // The request was made but no response was received
        console.error('Error request:', error.request);
      } else {
        // Something happened in setting up the request that triggered an Error
        console.error('Error message:', error.message);
      }
      setAvailableReports([]);
    }
  };

  const fetchReport = async (dateValue, forceRefresh = false) => {
    setLoading(true);
    setError(null);
    try {
      console.log(`Fetching ${reportType} report for date:`, dateValue, forceRefresh ? '(forcing refresh)' : '');
      
      let endpoint = 'daily-report';
      if (reportType !== 'daily') {
        endpoint = `${reportType}-report`;
      }
      
      const response = await axios.get(`http://localhost:8000/api/reports/${endpoint}`, {
        // Add cache-busting parameter to prevent browser caching
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' },
        params: { 
          date: dateValue,
          force_refresh: forceRefresh,
          _t: new Date().getTime() // Add timestamp to prevent caching
        }
      });
      console.log("Raw response data:", response.data);
      
      // Check if the selected report is a CSV or HTML file
      if (selectedReport && (selectedReport.filename.endsWith('.csv') || selectedReport.filename.endsWith('.html'))) {
        // For CSV and HTML files, we need to handle them differently
        if (selectedReport.filename.endsWith('.csv')) {
          // For CSV files, we'll show a message and a download link
          setReport({
            is_csv: true,
            filename: selectedReport.filename,
            path: selectedReport.path,
            markdown_report: `# CSV Report Available\n\nThis report is in CSV format. Please use the 'Export as CSV' button to download it.`
          });
        } else if (selectedReport.filename.endsWith('.html')) {
          // For HTML files, use the serve-file endpoint
          console.log("Selected HTML report:", selectedReport.filename);
          const fileUrl = `http://localhost:8000/api/reports/serve-file/${reportType}/${selectedReport.filename}`;
          console.log("Using HTML report URL:", fileUrl);
          
          // Set the report with the direct URL to the file
          setReport({
            html_report_url: fileUrl,
            html_report: null, // We're not loading the HTML content directly anymore
            markdown_report: null
          });
          setError(null);
        }
      } else {
        // Standard JSON report handling
        if (response.data.report) {
          console.log("Report found in response.data.report");
          // For daily reports, the actual content is nested inside the 'report' property
          const reportData = response.data.report;
          console.log("Report data structure:", Object.keys(reportData));
          
          // Make sure we have the expected data structure
          if (reportData.executive_summary || reportData.markdown_report) {
            console.log("Found expected report structure");
            setReport(reportData);
            setError(null);
          } else {
            console.log("Unexpected report structure, using as-is");
            setReport(reportData);
            setError(null);
          }
        } else if (response.data.message) {
          console.log("Message found in response:", response.data.message);
          setError(response.data.message);
          setReport(null);
        } else if (response.data.error) {
          console.log("Error found in response:", response.data.error);
          setError(response.data.error);
          setReport(null);
        } else if (response.data.executive_summary || response.data.markdown_report) {
          // Direct report data in response
          console.log("Direct report data found in response");
          setReport(response.data);
          setError(null);
        } else {
          // Fallback for unexpected format
          console.log("Unexpected data format, trying to use as is");
          setReport(response.data);
          setError(null);
        }
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
    console.log("Date changed to:", newDate);
    setSelectedDate(newDate);
    fetchReport(newDate.toLocaleDateString('en-CA'), false);
  };

  const handleReportTypeChange = (event) => {
    const newReportType = event.target.value;
    console.log("Report type changed to:", newReportType);
    setReportType(newReportType);
    setSelectedReport(null);
    
    // Reset the date selection for non-daily reports
    if (newReportType !== 'daily') {
      setSelectedDate(new Date());
    }
  };

  const handleGenerateReport = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log(`Generating ${reportType} report for date:`, selectedDate.toLocaleDateString('en-CA'));
      
      const dateValue = selectedDate.toLocaleDateString('en-CA');
      
      // For most report types, we can just use the regular fetchReport with force_refresh=true
      if (reportType !== 'daily') {
        // Fetch the report with force_refresh=true for weekly and other reports
        await fetchReport(dateValue, true);
        return;
      }
      
      // Special handling for daily reports which use a different endpoint
      const endpoint = 'force-daily-report';
      const method = 'post';
      const data = { params: { date: dateValue } };
      
      console.log(`Using endpoint: ${endpoint}, method: ${method}, data:`, data);
      
      const response = await axios({
        method: method,
        url: `http://localhost:8000/api/reports/${endpoint}`,
        ...data
      });
      
      console.log(`${reportType} report generated:`, response.data);
      
      if (response.data.success) {
        // Refresh the report list and fetch the newly generated report
        await fetchAvailableReports();
        await fetchReport(selectedDate.toLocaleDateString('en-CA'));
      } else if (response.data.message) {
        setError(response.data.message);
      } else if (response.data.error) {
        setError(response.data.error);
      }
    } catch (error) {
      console.error(`Error generating ${reportType} report:`, error);
      setError(error.message);
      
      // If the server is still processing, wait and try again
      if (error.response && error.response.status === 503) {
        console.log("Server is still processing, waiting to try again...");
        setTimeout(() => fetchReport(selectedDate.toLocaleDateString('en-CA')), 3000);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = () => {
    if (selectedReport && selectedReport.path) {
      // Use the serve-file endpoint to download the CSV file
      const fileUrl = `http://localhost:8000/api/reports/serve-file/${reportType}/${selectedReport.filename}`;
      window.open(fileUrl, '_blank');
    }
  };

  const downloadCSV = (path, filename) => {
    // Use the serve-file endpoint to download the CSV file
    const fileUrl = `http://localhost:8000/api/reports/serve-file/${reportType}/${filename}`;
    window.open(fileUrl, '_blank');
  };

  const handleReportSelect = (reportItem) => {
    console.log("Selected report:", reportItem);
    setSelectedReport(reportItem);
    
    if (reportItem) {
      console.log("Report filename:", reportItem.filename);
      
      // Handle different file types
      if (reportItem.filename.endsWith('.csv')) {
        // For CSV files, we'll show a message and a download link
        console.log("Selected CSV report:", reportItem.filename);
        setReport({
          is_csv: true,
          filename: reportItem.filename,
          path: reportItem.path,
          markdown_report: `# CSV Report Available\n\nThis report is in CSV format. Please use the 'Export as CSV' button to download it.`
        });
      } else if (reportItem.filename.endsWith('.html')) {
        // For HTML files, use the serve-file endpoint
        console.log("Selected HTML report:", reportItem.filename);
        const fileUrl = `http://localhost:8000/api/reports/serve-file/${reportType}/${reportItem.filename}`;
        console.log("Using HTML report URL:", fileUrl);
        
        // Set the report with the direct URL to the file
        setReport({
          html_report_url: fileUrl,
          html_report: null, // We're not loading the HTML content directly anymore
          markdown_report: null
        });
        setError(null);
      } else {
        // For JSON reports, extract the date and fetch
        if (reportType === 'daily') {
          // Extract date from filename (format: 2025-03-13_report.json)
          const dateStr = reportItem.filename.split('_')[0];
          console.log("Extracted date from daily report filename:", dateStr);
          
          if (dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
            console.log("Valid date format found, setting date and fetching report");
            const newDate = new Date(dateStr);
            setSelectedDate(newDate);
            setSelectedReport(reportItem);
            
            // Use the direct serve-file endpoint for JSON files
            const fileUrl = `http://localhost:8000/api/reports/serve-file/${reportType}/${reportItem.filename}`;
            console.log("Using JSON report URL:", fileUrl);
            
            // Fetch the JSON file directly
            axios.get(fileUrl)
              .then(response => {
                console.log("JSON report data:", response.data);
                setReport(response.data);
                setError(null);
              })
              .catch(error => {
                console.error("Error fetching JSON report:", error);
                setError(`Failed to load JSON report: ${error.message}`);
              });
          } else {
            console.error("Invalid date format in filename:", reportItem.filename);
          }
        } else if (reportItem.date_range) {
          // For other report types with date ranges
          console.log("Report has date range:", reportItem.date_range);
          // Extract the start date from the date range (format: 2025-03-10 to 2025-03-16)
          const dateStr = reportItem.date_range.split(' to ')[0];
          if (dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
            const newDate = new Date(dateStr);
            setSelectedDate(newDate);
            fetchReport(dateStr);
          }
        }
      }
    }
  };

  return (
    <div className="reports-page">
      <h1>Activity Reports</h1>
      
      <div style={{ display: 'flex', marginBottom: '20px' }}>
        {/* Report type selector */}
        <div style={{ marginRight: '20px' }}>
          <label htmlFor="report-type">Report Type: </label>
          <select 
            id="report-type" 
            value={reportType} 
            onChange={handleReportTypeChange}
            style={{ padding: '5px', borderRadius: '4px', border: '1px solid #ccc' }}
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="quarterly">Quarterly</option>
            <option value="annual">Annual</option>
          </select>
        </div>
        
        {/* Generate report button */}
        <button 
          onClick={handleGenerateReport} 
          disabled={loading}
          style={{ padding: '5px 10px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px' }}
        >
          Generate {reportType.charAt(0).toUpperCase() + reportType.slice(1)} Report
        </button>
        
        {/* Debug toggle */}
        <div style={{ marginLeft: 'auto' }}>
          <label>
            <input 
              type="checkbox" 
              checked={showDebugInfo} 
              onChange={(e) => setShowDebugInfo(e.target.checked)} 
            />
            Show Debug Info
          </label>
        </div>
      </div>
      
      <div style={{ display: 'flex' }}>
        {/* Left column - Calendar and available reports */}
        <div style={{ flex: '1', marginRight: '20px' }}>
          <h2>Select Date</h2>
          <Calendar 
            onChange={handleDateChange} 
            value={selectedDate} 
            className="reports-calendar"
          />
          
          <div className="available-reports">
            <h2>Available {reportType.charAt(0).toUpperCase() + reportType.slice(1)} Reports</h2>
            {availableReports.length === 0 ? (
              <p>No reports available.</p>
            ) : (
              <ul className="reports-list">
                {availableReports.map((reportItem, index) => (
                  <li 
                    key={index} 
                    className={selectedReport && selectedReport.filename === reportItem.filename ? 'selected' : ''}
                    onClick={() => handleReportSelect(reportItem)}
                  >
                    {reportItem.filename}
                    {reportItem.date_range && <span className="date-range"> ({reportItem.date_range})</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        
        {/* Right column - Report content */}
        <div style={{ flex: '2' }}>
          {loading && <p>Loading report...</p>}
          {error && <p style={{ color: 'red' }}>{error}</p>}
          
          {!loading && !error && (
            <div className="report-content">
              {/* Debug information panel */}
              {showDebugInfo && (
                <div style={{ padding: '15px', backgroundColor: '#f5f5f5', marginBottom: '20px', borderRadius: '5px', fontSize: '0.9em' }}>
                  <h3 style={{ marginTop: '0' }}>Report Debug Info:</h3>
                  <p>Selected Date: {selectedDate.toLocaleDateString('en-CA')}</p>
                  <p>Report Type: {reportType}</p>
                  <p>Selected Report: {selectedReport ? selectedReport.filename : 'none'}</p>
                  <p>Report Keys: {report ? Object.keys(report).join(', ') : 'N/A'}</p>
                  <p>Has html_report: {report && report.html_report ? 'true' : 'false'}</p>
                  <p>Has html_report_url: {report && report.html_report_url ? 'true' : 'false'}</p>
                  <p>HTML URL: {report && report.html_report_url ? report.html_report_url : 'None'}</p>
                  <p>Has markdown_report: {report && report.markdown_report ? 'true' : 'false'}</p>
                  <p>Has executive_summary: {report && report.executive_summary ? 'true' : 'false'}</p>
                </div>
              )}
              
              {/* Show a message when there's no report */}
              {!report && <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #ddd', borderRadius: '5px' }}>
                <p>No report data available. Try generating a report first.</p>
              </div>}
              
              {report && (
              <>
              {/* Debug info - visible for troubleshooting */}
              {showDebugInfo && (
              <div style={{ display: 'block', backgroundColor: '#f8f9fa', padding: '10px', marginBottom: '15px', border: '1px solid #ddd', borderRadius: '5px' }}>
                <p><strong>Report Debug Info:</strong></p>
                <p>Report keys: {Object.keys(report).join(', ')}</p>
                <p>Has html_report: {String(Boolean(report.html_report))}</p>
                <p>Has html_report_url: {String(Boolean(report.html_report_url))}</p>
                <p>HTML URL: {report.html_report_url || 'None'}</p>
                <p>Has markdown_report: {String(Boolean(getReportValue(report, 'markdown_report')))}</p>
                <p>Has executive_summary: {String(Boolean(getExecutiveSummary(report)))}</p>
                <p>Report Type: {reportType}</p>
              </div>
              )}
              
              {report.is_csv ? (
                <div className="csv-report">
                  <h2>CSV Report Available</h2>
                  <p>This report is in CSV format. Use the 'Export as CSV' button to download it.</p>
                  <button 
                    onClick={handleExportCSV}
                    style={{ padding: '10px 15px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px' }}
                  >
                    Download CSV Report
                  </button>
                </div>
              ) : report.html_report_url || (report.html_report && report.html_report.length > 0) ? (
                <div className="html-report">
                  <iframe 
                    src={report.html_report_url || null}
                    srcDoc={!report.html_report_url && report.html_report ? report.html_report : null}
                    className="html-report-content"
                    style={{ width: '100%', height: '800px', border: 'none' }}
                    title={`${reportType.charAt(0).toUpperCase() + reportType.slice(1)} Report`}
                    sandbox="allow-scripts"
                  />
                </div>
              ) : getReportValue(report, 'markdown_report') ? (
                <div className="markdown-report">
                  <h2>{reportType.charAt(0).toUpperCase() + reportType.slice(1)} Report Content</h2>
                  <div style={{ border: '1px solid #ddd', padding: '15px', borderRadius: '5px', marginBottom: '20px', backgroundColor: 'white' }}>
                    <ReactMarkdown>{getReportValue(report, 'markdown_report')}</ReactMarkdown>
                  </div>
                  
                  {getExecutiveSummary(report) && (
                    <div className="executive-summary" style={{ border: '1px solid #ddd', padding: '15px', borderRadius: '5px', marginBottom: '20px' }}>
                      <h2>Executive Summary</h2>
                      <p><strong>Total Time:</strong> {getExecutiveSummary(report).total_time} minutes</p>
                  
                      {getExecutiveSummary(report).time_by_group && Object.keys(getExecutiveSummary(report).time_by_group).length > 0 && (
                        <div>
                          <h3>Time by Group</h3>
                          <ul>
                            {Object.entries(getExecutiveSummary(report).time_by_group).map(([group, time]) => (
                              <li key={group}><strong>{group}:</strong> {time} minutes</li>
                            ))}
                          </ul>
                        </div>
                      )}
                  
                      {getExecutiveSummary(report).time_by_category && Object.keys(getExecutiveSummary(report).time_by_category).length > 0 && (
                        <div>
                          <h3>Time by Category</h3>
                          <ul>
                            {Object.entries(getExecutiveSummary(report).time_by_category).map(([category, time]) => (
                              <li key={category}><strong>{category}:</strong> {time} minutes</li>
                            ))}
                          </ul>
                        </div>
                      )}
                  
                      {getExecutiveSummary(report).progress_report && (
                        <div>
                          <h3>Progress Report</h3>
                          <p>{getExecutiveSummary(report).progress_report}</p>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {getReportValue(report, 'details') && getReportValue(report, 'details').length > 0 && (
                    <div className="report-details" style={{ border: '1px solid #ddd', padding: '15px', borderRadius: '5px' }}>
                      <h2>Activity Details</h2>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Group</th>
                            <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Time</th>
                            <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {getReportValue(report, 'details').map((activity, index) => (
                            <tr key={index}>
                              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{activity.group}</td>
                              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{activity.duration_minutes} minutes</td>
                              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{activity.description}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ padding: '20px', backgroundColor: '#f8f9fa', border: '1px solid #ddd', borderRadius: '5px' }}>
                  <p>No report content available in the expected format.</p>
                  <p>Raw data: {JSON.stringify(report, null, 2)}</p>
                </div>
              )}
              </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReportsPage;
