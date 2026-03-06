# Smart Health Appointment System

An academic project demonstrating a full-stack appointment scheduling system with AI-powered symptom analysis.

## Features

- **AI Symptom Analysis**: Uses a Naive Bayes classifier (simulated ML pipeline) to analyze natural language symptoms and recommend the appropriate medical department.
- **Smart Slot Booking**: View available slots for the recommendation.
- **Landing Page**: detailed introduction with premium animations.
- **Routing**: Client-side routing with `react-router-dom`.

## Project Structure

- **frontend/**: React application using Vite.
  - **components/**: Reusable UI blocks (Footer, Header, LoadingScreen).
  - **pages/**: Route views (LandingPage, MainApp).
- **backend/**: FastAPI application with ML logic.

## Setup & Running

### Prerequisites
- Node.js
- Python 3.8+

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
The API will be available at `http://localhost:8000`.

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The App will be available at `http://localhost:5173`.

## Usage
1. **Landing Page**: Open the app to see the introduction.
2. **Book Checkup**: Click "Start Checkup" to enter the main app.
3. **Analyze**: Enter symptoms (e.g., "Severe headache").
4. **Book**: Select a slot and confirm.
