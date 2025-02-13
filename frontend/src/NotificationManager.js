// src/NotificationManager.js
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const NotificationManager = () => {
  const navigate = useNavigate();
  const [intervalMs, setIntervalMs] = useState(60000); // default to 1 minute

  // Fetch settings and update the notification interval
  useEffect(() => {
    axios.get('http://localhost:8000/api/settings')
      .then(response => {
        const minutes = response.data.notificationInterval; // Assume it's returned in minutes
        setIntervalMs(minutes * 60000); // Convert minutes to milliseconds
        console.log("Notification interval set to", minutes, "minutes");
      })
      .catch(error => {
        console.error("Error fetching settings:", error);
      });
  }, []);

  useEffect(() => {
    // Request notification permission if not already granted.
    if (Notification.permission !== 'granted') {
      Notification.requestPermission().then(permission => {
        console.log("Notification permission:", permission);
      });
    }
    const notificationInterval = setInterval(() => {
      if (Notification.permission === 'granted') {
        const notification = new Notification('ActivityLogger', {
          body: 'Time to record your activity!',
          requireInteraction: true, // Keeps notification until interaction
        });
        notification.onclick = () => {
          window.focus();
          navigate('/');
          notification.close();
        };
      }
    }, intervalMs);

    return () => clearInterval(notificationInterval);
  }, [navigate, intervalMs]);

  return null;
};

export default NotificationManager;