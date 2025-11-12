# VANET Frontend

This is a minimal React frontend (Vite) that provides two buttons to select the control method used by the simulation: RL-based or Rule-based.

Quick start:

1. cd frontend
2. npm install
3. npm run dev

The UI will try to POST to `http://localhost:5000/api/method`. Make sure the backend is running and CORS is enabled (the existing backend already enables CORS).
