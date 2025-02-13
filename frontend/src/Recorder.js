// frontend/src/components/Recorder.js
import React, { useState, useRef } from 'react';
import axios from 'axios';

const Recorder = () => {
  const [recording, setRecording] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [mediaStream, setMediaStream] = useState(null); // New state for the stream
  const audioChunksRef = useRef([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setMediaStream(stream); // Save the stream so we can stop it later
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = event => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.start();
      setMediaRecorder(recorder);

      // Request a session id from the backend.
      const response = await axios.post('http://localhost:8000/api/recording/start');
      console.log("Received session id:", response.data.session_id);
      setSessionId(response.data.session_id);
      setRecording(true);
    } catch (error) {
      console.error("Error starting recording:", error);
    }
  };

  const stopRecording = async () => {
    if (!mediaRecorder) {
      console.error("No mediaRecorder available.");
      return;
    }

    mediaRecorder.onstop = async () => {
      // Stop all tracks of the media stream to free up the device.
      if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        setMediaStream(null);
      }

      // Use the actual MIME type from the recorder (or default to 'audio/webm')
      const mimeType = mediaRecorder.mimeType || 'audio/webm';
      const fileExtension = mimeType.includes('webm') ? 'webm'
                           : mimeType.includes('ogg') ? 'ogg'
                           : 'wav';  // fallback
      
      const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
      
      // Create FormData and append the recorded audio and session_id.
      const formData = new FormData();
      formData.append("file", audioBlob, `recording.${fileExtension}`);
      formData.append("session_id", sessionId);

      try {
        const response = await axios.post('http://localhost:8000/api/recording/stop', formData);
        setRecording(false);
        console.log(response.data.message);
      } catch (error) {
        console.error("Error stopping recording:", error);
      }
    };

    mediaRecorder.stop();
  };

  return (
    <div style={{ padding: '20px', textAlign: 'center' }}>
      <h1>ActivityReport Recorder</h1>
      {recording ? (
        <button onClick={stopRecording} style={{ padding: '10px 20px', fontSize: '16px' }}>
          Stop Recording
        </button>
      ) : (
        <button onClick={startRecording} style={{ padding: '10px 20px', fontSize: '16px' }}>
          Start Recording
        </button>
      )}
      {sessionId && (
        <p style={{ marginTop: '20px', fontStyle: 'italic' }}>Session ID: {sessionId}</p>
      )}
    </div>
  );
};

export default Recorder;