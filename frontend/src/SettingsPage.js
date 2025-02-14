import React, { useState, useEffect } from 'react';
import axios from 'axios';

const SettingsPage = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // Fetch settings from the backend on mount
  useEffect(() => {
    axios.get('http://localhost:8000/api/settings')
      .then((res) => {
        setSettings(res.data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching settings:", err);
        setMessage("Error fetching settings");
        setLoading(false);
      });
  }, []);

  const handleOtherSettingChange = (field, value) => {
    setSettings((prev) => ({ ...prev, [field]: value }));
  };

  const handleCategoryNameChange = (index, newName) => {
    setSettings((prev) => {
      const newCategories = [...prev.categories];
      newCategories[index].name = newName;
      return { ...prev, categories: newCategories };
    });
  };

  const handleGroupsChange = (index, newValue) => {
    setSettings((prev) => {
      const newCategories = [...prev.categories];
      
      // Split and clean groups, preserving empty trailing input
      const groups = newValue.split(',');
      const cleanedGroups = groups.map(group => group.trim());
      
      // Remove empty groups except for the last one (allows typing)
      const finalGroups = groups.length > 1 
        ? [...cleanedGroups.slice(0, -1).filter(g => g !== ''), cleanedGroups[cleanedGroups.length - 1]]
        : cleanedGroups;
      
      newCategories[index].groups = finalGroups;
      return { ...prev, categories: newCategories };
    });
  };

  const handleSave = async () => {
    try {
      const cleanedSettings = {
        ...settings,
        categories: settings.categories.map(category => ({
          ...category,
          groups: category.groups
            .filter(group => group && group.trim() !== '')
        }))
      };

      const response = await axios.put('http://localhost:8000/api/settings', cleanedSettings);
      setSettings(response.data);
      setMessage("Settings updated successfully");
      setError("");
    } catch (err) {
      console.error("Error saving settings:", err);
      setError(err.response?.data?.detail || "Error saving settings");
    }
  };

  if (loading) return <p>Loading settings...</p>;
  if (!settings) return <p>Error loading settings.</p>;

  return (
    <div style={{ padding: '20px' }}>
      <h1>Settings</h1>
      
      <div style={{ marginBottom: '20px' }}>
        <label>
          Notification Interval (minutes):{' '}
          <input 
            type="number" 
            value={settings.notificationInterval} 
            onChange={(e) => handleOtherSettingChange("notificationInterval", parseInt(e.target.value))}
          />
        </label>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label>
          Audio Device:{' '}
          <input 
            type="text" 
            value={settings.audioDevice} 
            onChange={(e) => handleOtherSettingChange("audioDevice", e.target.value)}
          />
        </label>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label>
          LLM Provider:{' '}
          <input 
            type="text" 
            value={settings.llmProvider} 
            onChange={(e) => handleOtherSettingChange("llmProvider", e.target.value)}
          />
        </label>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h2>Categories and Groups</h2>
        {settings.categories && settings.categories.map((category, index) => (
          <div key={index} style={{ 
            border: '1px solid #ccc', 
            padding: '15px', 
            marginBottom: '15px',
            borderRadius: '5px',
            backgroundColor: '#f9f9f9'
          }}>
            <div>
              <strong>Category Name:</strong>{' '}
              <input 
                type="text" 
                value={category.name} 
                onChange={(e) => handleCategoryNameChange(index, e.target.value)}
                style={{ 
                  marginLeft: '10px',
                  padding: '5px',
                  borderRadius: '3px',
                  border: '1px solid #ddd'
                }}
              />
            </div>
            <div style={{ marginTop: '10px' }}>
              <strong>Groups:</strong>{' '}
              <input 
                type="text" 
                value={category.groups.join(', ')}
                onChange={(e) => handleGroupsChange(index, e.target.value)}
                style={{ 
                  marginLeft: '10px',
                  width: '80%',
                  padding: '5px',
                  borderRadius: '3px',
                  border: '1px solid #ddd'
                }}
                placeholder="Enter groups separated by commas"
              />
              <div style={{ 
                fontSize: '0.8em',
                color: '#666',
                marginTop: '5px',
                marginLeft: '10px'
              }}>
                Separate groups with commas. Type and press Enter to save changes.
              </div>
            </div>
          </div>
        ))}
      </div>

      <button 
        onClick={handleSave}
        style={{
          padding: '10px 20px',
          backgroundColor: '#4CAF50',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer'
        }}
      >
        Save Settings
      </button>

      {error && <p style={{ color: 'red', marginTop: '10px' }}>{error}</p>}
      {message && <p style={{ color: 'green', marginTop: '10px' }}>{message}</p>}
    </div>
  );
};

export default SettingsPage;