// frontend/src/components/Recorder.js
import React, { useState, useRef } from 'react';
import axios from 'axios';

const Recorder = () => {
  const [recording, setRecording] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [mediaStream, setMediaStream] = useState(null);
  const [processing, setProcessing] = useState(false);
  const audioChunksRef = useRef([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setMediaStream(stream);
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = event => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.start();
      setMediaRecorder(recorder);

      const response = await axios.post('http://localhost:8000/api/recording/start');
      console.log("Received session id:", response.data.session_id);
      setSessionId(response.data.session_id);
      setRecording(true);
    } catch (error) {
      console.error("Error starting recording:", error);
    }
  };

  const stopRecording = () => {
    if (!mediaRecorder) {
      console.error("No mediaRecorder available.");
      return;
    }
    
    // Set processing to true immediately on stop click
    setProcessing(true);
    setRecording(false);
    
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      setMediaStream(null);
    }

    // Set up the onstop handler before calling stop()
    mediaRecorder.onstop = async () => {
      const mimeType = mediaRecorder.mimeType || 'audio/webm';
      const fileExtension = mimeType.includes('webm') ? 'webm'
                           : mimeType.includes('ogg') ? 'ogg'
                           : 'wav';

      const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });

      const formData = new FormData();
      formData.append("file", audioBlob, `recording.${fileExtension}`);
      formData.append("session_id", sessionId);

      try {
        const response = await axios.post('http://localhost:8000/api/recording/stop', formData);
        console.log(response.data.message);
        setProcessing(false); // Only set processing to false after backend confirms
      } catch (error) {
        console.error("Error stopping recording:", error);
        setProcessing(false); // Also set processing to false if there's an error
      }
    };

    // Call stop() after setting up the handler
    mediaRecorder.stop();
  };

  return (
    <div style={{ padding: '20px', textAlign: 'center' }}>
      <h1>ActivityReport Recorder</h1>
      <div style={{ display: 'flex', justifyContent: 'center' }}> {/* Center the button */}
        {recording ? (
          <div
            onClick={stopRecording}
            style={{
              width: '150px', // Increased size
              height: '150px', // Increased size
              borderRadius: '50%',
              backgroundColor: 'red',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              color: 'white',
              cursor: 'pointer',
              fontSize: '18px', // Slightly larger font
               boxShadow: '0 0 20px red' // Added motion effect
            }}
          >
            Stop / Recording
          </div>
        ) : processing ? (
          <div
            style={{
              width: '150px', // Increased size
              height: '150px', // Increased size
              borderRadius: '50%',
              backgroundColor: 'blue', // Changed from grey to blue as requested
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              color: 'white',
              fontSize: '18px', // Slightly larger font
            }}
          >
            Post-processing / activities
          </div>
        ) : (
          <div
            onClick={startRecording}
            style={{
              width: '150px', // Increased size
              height: '150px', // Increased size
              borderRadius: '50%',
              backgroundColor: 'green',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              color: 'white',
              cursor: 'pointer',
              fontSize: '18px', // Slightly larger font
            }}
          >
            Start / Recording
          </div>
        )}
      </div>
      {sessionId && (
        <p style={{ marginTop: '20px', fontStyle: 'italic' }}>Session ID: {sessionId}</p>
      )}
    </div>
  );
};

export default Recorder;