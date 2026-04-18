# Smart Health - Backend API (FastAPI)

AI-powered healthcare platform backend using FastAPI, MongoDB (Motor), and Gemini AI.

## Features
- **AI Triage**: Predicts department and priority based on symptoms.
- **Dynamic Scheduling**: Manages doctor availability and real-time slots.
- **Secure Messaging**: Participant-verified private chat channels.
- **Payment Integration**: Razorpay-ready booking flow.
- **Machine Learning**: No-show prediction and doctor recommendations.

## Prerequisites
- Python 3.9+
- MongoDB instance (Local or Atlas)
- Google OAuth Client (for GSI login)
- Razorpay Account (for payments)
- Gemini API Key (for AI summaries)

## Installation

1. **Clone the repository**
   ```bash
   cd backend
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\\Scripts\\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   Create a `.env` file in the `backend` directory based on `.env.example`.

5. **Run the server**
   ```bash
   uvicorn main:app --reload
   ```
   The API will be available at `http://localhost:8000`.

## Environment Variables
| Variable | Description |
|----------|-------------|
| `MONGO_URI` | MongoDB connection string |
| `JWT_SECRET` | Secret key for local token generation |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID from Google Cloud |
| `RAZORPAY_KEY_ID` | Your Razorpay test/live key ID |
| `RAZORPAY_KEY_SECRET` | Your Razorpay test/live secret |
| `GEMINI_API_KEY` | Google AI Studio key for summaries |
| `MAIL_USERNAME` | SMTP username for email notifications |
| `MAIL_PASSWORD` | SMTP password |
