// src/SettingsPage.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const SettingsPage = () => {
  // Default settings
  const [settings, setSettings] = useState({
    notificationInterval: 15,
    audioDevice: "default",
    llmProvider: "LMStudio",
    openRouterApiKey: "",
    openRouterLLM: "",
    activityGroups: "coding, meeting, research, others"
  });
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  // Fetch settings on component mount.
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/settings');
        // Assume the API returns an object with matching keys.
        setSettings(response.data);
      } catch (error) {
        console.error("Error fetching settings:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, []);

  // Handle form input changes.
  const handleChange = (e) => {
    const { name, value } = e.target;
    setSettings(prevSettings => ({
      ...prevSettings,
      [name]: value
    }));
  };

  // Submit the updated settings to the API.
  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.put('http://localhost:8000/api/settings', settings);
      setMessage("Settings updated successfully.");
      setSettings(response.data);
    } catch (error) {
      console.error("Error updating settings:", error);
      setMessage("Error updating settings.");
    }
  };

  if (loading) return <div>Loading settings...</div>;

  return (
    <div style={{ padding: '20px' }}>
      <h1>Settings</h1>
      {message && <p>{message}</p>}
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '15px' }}>
          <label>
            Notification Interval (minutes):
            <select 
              name="notificationInterval" 
              value={settings.notificationInterval} 
              onChange={handleChange}
              style={{ marginLeft: '10px' }}
            >
              <option value={1}>1 (debug)</option>
              <option value={15}>15</option>
              <option value={30}>30</option>
              <option value={60}>60</option>
              <option value={120}>120</option>
            </select>
          </label>
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label>
            Audio Device:
            <input 
              type="text" 
              name="audioDevice" 
              value={settings.audioDevice} 
              onChange={handleChange} 
              disabled 
              style={{ marginLeft: '10px' }}
            />
            <small> (Default device in use)</small>
          </label>
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label>
            LLM Provider:
            <select 
              name="llmProvider" 
              value={settings.llmProvider} 
              onChange={handleChange}
              style={{ marginLeft: '10px' }}
            >
              <option value="LMStudio">LMStudio</option>
              <option value="Ollama">Ollama</option>
              <option value="OpenRouter">OpenRouter</option>
              <option value="OpenAI">OpenAI</option>
              <option value="DeepSeek">DeepSeek</option>
              <option value="Gemini">Gemini</option>
              <option value="Claude">Claude</option>
            </select>
          </label>
        </div>
        {settings.llmProvider === "OpenRouter" && (
          <>
            <div style={{ marginBottom: '15px' }}>
              <label>
                OpenRouter API Key:
                <input 
                  type="text" 
                  name="openRouterApiKey" 
                  value={settings.openRouterApiKey} 
                  onChange={handleChange}
                  style={{ marginLeft: '10px' }}
                />
              </label>
            </div>
            <div style={{ marginBottom: '15px' }}>
              <label>
                OpenRouter LLM:
                <input 
                  type="text" 
                  name="openRouterLLM" 
                  value={settings.openRouterLLM} 
                  onChange={handleChange}
                  style={{ marginLeft: '10px' }}
                />
              </label>
            </div>
          </>
        )}
        <div style={{ marginBottom: '15px' }}>
          <label>
            Activity Groups (comma-separated):
            <input 
              type="text" 
              name="activityGroups" 
              value={settings.activityGroups} 
              onChange={handleChange}
              style={{ marginLeft: '10px', width: '300px' }}
            />
          </label>
        </div>
        <button type="submit" style={{ padding: '8px 16px' }}>Save Settings</button>
      </form>
    </div>
  );
};

export default SettingsPage;