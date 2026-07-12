# AutoVision: AI-Powered Video Surveillance Platform

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-19+-61DAFB.svg)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![Supabase](https://img.shields.io/badge/Supabase-Database-3FCF8E.svg)](https://supabase.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

AutoVision is a production-ready AI-powered video surveillance platform that combines advanced computer vision, reinforcement learning, and RAG (Retrieval-Augmented Generation) systems to provide intelligent video analysis and anomaly detection.

**LIVE SITE** : [https://autovision-ai.onrender.com](https://autovision-ai.onrender.com)
## 🎯 Key Features

### 🤖 AI-Powered Analysis

- **Advanced Anomaly Detection**: Pretrained CNN (MobileNetV2 via ONNX Runtime) appearance embeddings combined with OpenCV motion analysis - chosen to fit free-tier hosting memory limits
- **Reinforcement Learning**: Adaptive learning system that improves detection accuracy over time
- **RAG System**: Intelligent pattern recognition and contextual analysis
- **Real-time Processing**: Automatic video processing upon upload

### 🔐 Enterprise Security

- **Supabase Authentication**: Secure user management with email verification
- **Row-Level Security (RLS)**: Database-level access control
- **JWT Token Authentication**: Secure API access
- **Role-based Permissions**: Fine-grained access control

### 🎥 Video Management

- **Cloud Storage**: Supabase Storage integration with automatic backup
- **Automatic Cleanup**: Configurable video retention policies
- **Secure Streaming**: Protected video playback with signed URLs
- **Multiple Format Support**: MP4, AVI, MOV, and more

### 📊 Analytics & Insights

- **Real-time Dashboard**: Live video processing statistics
- **Event Timeline**: Detailed anomaly detection history
- **Performance Metrics**: Processing time, accuracy, and system health
- **User Settings**: Customizable retention and processing preferences

### 🚀 Production Ready

- **Cloud Deployment**: Optimized for Render, Vercel, and other platforms
- **Scalable Architecture**: Async processing with background tasks
- **Error Handling**: Comprehensive logging and error recovery
- **Database Migrations**: Complete SQL setup scripts

## 🏗️ Architecture

### Backend (FastAPI)

```
backend/
├── main.py              # Application entry point
├── api_routes.py        # REST API endpoints
├── auth.py             # Authentication middleware
├── video_processor.py   # Video processing pipeline
├── video_cleanup.py     # Automated cleanup service
├── autovision_client.py # Supabase integration
└── ai_models/          # AI/ML components
    ├── ml_anomaly_detector.py   # Real detector: MobileNetV2 (ONNX) + OpenCV motion analysis
    ├── simple_anomaly_detector.py # Legacy random-score fallback (USE_PRETRAINED_MODELS=false)
    ├── simple_rl_controller.py
    └── simple_rag_system.py
```

### Frontend (React + TypeScript)

```
frontend/src/
├── App.tsx             # Main application component
├── components/         # Reusable UI components
├── pages/             # Application pages
├── contexts/          # React contexts (Auth)
├── hooks/             # Custom React hooks
└── lib/               # Utilities and API client
```

### Database (Supabase PostgreSQL)

```sql
-- Core Tables
user_profiles          # User account information
videos                # Video metadata and storage
events                # Anomaly detection events
user_settings         # Configurable user preferences

-- Storage Buckets
video-uploads         # Secure video file storage
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Supabase Account** (free tier works)
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/autovision.git
cd autovision
```

### 2. Setup Supabase Database

1. Create a new Supabase project at [supabase.com](https://supabase.com)
2. Get your project URL and anon key from the API settings
3. Run the canonical setup script (idempotent - safe to re-run):

```sql
-- In Supabase SQL Editor, run:
\i supabase/schema.sql
```

(`supabase/deprecated/` holds the older `complete_production_setup.sql` /
`quick_production_setup.sql` / `troubleshooting_fixes.sql` scripts this
replaced - kept for historical reference only, do not run them.)

### 3. Environment Configuration

Backend and frontend each keep their own env file, alongside their own code:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

`backend/.env`:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# JWT Secret (use a strong random string)
JWT_SECRET=your_jwt_secret_key

# Environment
ENVIRONMENT=development
```

`frontend/.env` (only needed for production builds/preview - `npm run dev` uses
the Vite proxy in `vite.config.js` instead):

```bash
VITE_API_URL=http://localhost:12000/api/v1
```

### 4. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Start the backend server
python main.py
```

The backend will be available at `http://localhost:8000`

### 5. Frontend Setup

```bash
# Install Node.js dependencies
cd frontend
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

## 🔧 Configuration

### User Settings

Users can configure the following through the web interface:

- **Video Retention Period**: How long to keep videos (1-365 days)
- **Auto-cleanup**: Enable/disable automatic video deletion
- **Processing Preferences**: AI model selection and sensitivity

### Environment Variables

| Variable                     | Description                                          | Required |
| ---------------------------- | ----------------------------------------------------- | -------- |
| `SUPABASE_URL`                | Your Supabase project URL                              | ✅       |
| `SUPABASE_ANON_KEY`           | Supabase anon key                                      | ✅       |
| `SUPABASE_SERVICE_ROLE_KEY`   | Service role key for admin operations                  | ✅       |
| `JWT_SECRET`                  | Secret for JWT token signing                           | ✅       |
| `ENVIRONMENT`                 | Environment (development/production)                   | ❌       |
| `CORS_ALLOWED_ORIGINS`        | Comma-separated allowed frontend origins               | ❌       |
| `USE_PRETRAINED_MODELS`       | Use the real ML detector vs. legacy demo detector       | ❌       |
| `SYSTEM_ADMIN_EMAILS`         | Comma-separated emails provisioned as system/admin users | ❌       |

## 📊 API Documentation

### Authentication Endpoints

| Method | Endpoint       | Description              |
| ------ | -------------- | ------------------------ |
| POST   | `/auth/signup` | Create new user account  |
| POST   | `/auth/login`  | User authentication      |
| POST   | `/auth/logout` | User logout              |
| GET    | `/auth/me`     | Get current user profile |

### Video Management

| Method | Endpoint              | Description              |
| ------ | --------------------- | ------------------------ |
| POST   | `/videos/upload`      | Upload and process video |
| GET    | `/videos`             | List user's videos       |
| GET    | `/videos/{id}`        | Get video details        |
| GET    | `/videos/{id}/stream` | Stream video content     |
| DELETE | `/videos/{id}`        | Delete video             |

### Analytics & Events

| Method | Endpoint           | Description               |
| ------ | ------------------ | ------------------------- |
| GET    | `/events`          | List anomaly events       |
| GET    | `/analytics/stats` | Get processing statistics |
| GET    | `/system/status`   | System health check       |

### User Settings

| Method | Endpoint    | Description          |
| ------ | ----------- | -------------------- |
| GET    | `/settings` | Get user settings    |
| PUT    | `/settings` | Update user settings |

## 🚀 Deployment

### Render Deployment

1. **Fork the repository** to your GitHub account

2. **Create a new Web Service** on Render:

   - Connect your GitHub repository
   - Set build command: `pip install -r backend/requirements.txt`
   - Set start command: `cd backend && python main.py`
   - Add environment variables from your `backend/.env` file

3. **Deploy Frontend** to Vercel/Netlify:
   - Connect your repository
   - Set build command: `cd frontend && npm run build`
   - Set build directory: `frontend/dist`
   - Add environment variables for Supabase

### Docker Deployment

```dockerfile
# Backend Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "backend/main.py"]
```

### Environment Setup

For production deployment, ensure these environment variables are set:

```bash
SUPABASE_URL=your_production_supabase_url
SUPABASE_ANON_KEY=your_production_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_production_service_role_key
JWT_SECRET=your_strong_jwt_secret
ENVIRONMENT=production
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
```

## 🧪 Testing

### Backend Tests

```bash
# Run all backend tests
cd backend
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_video_processor.py -v
```

### Frontend Tests

```bash
# Run frontend tests
cd frontend
npm test

# Run with coverage
npm run test:coverage
```

### Integration Testing

```bash
# Test video processing pipeline
python test_real_processing.py
```

## 🛠️ Development

### AI Model Development

The AI models are modular and can be extended:

```python
# Example: Adding a new anomaly detection model
from ai_models.base import BaseAnomalyDetector

class CustomAnomalyDetector(BaseAnomalyDetector):
    def detect_anomalies(self, video_path: str) -> List[dict]:
        # Your custom detection logic
        pass
```

### Database Migrations

`supabase/schema.sql` is the single canonical, idempotent schema definition -
re-run it any time to apply changes or reconcile drift:

```sql
\i supabase/schema.sql
```

### Adding New Features

1. **Backend**: Add new routes in `api_routes.py`
2. **Frontend**: Create components in `src/components/`
3. **Database**: Update schema and add migration script
4. **Tests**: Add tests for new functionality

## 📚 Project Structure

```
autovision/
├── README.md                    # This file
├── .slugignore                 # Render deployment config
├── cleanup.py                  # Development cleanup script
├── ai_models/                  # AI/ML models (shared by backend, not nested in it)
│   ├── ml_anomaly_detector.py
│   ├── simple_rl_controller.py
│   └── simple_rag_system.py
├── backend/                    # FastAPI backend
│   ├── .env.example            # Backend env template (copy to .env)
│   ├── requirements.txt        # Python dependencies
│   ├── main.py                # Application entry point
│   ├── api_routes.py          # REST API routes
│   ├── auth.py                # Authentication
│   ├── video_processor.py     # Video processing
│   ├── video_cleanup.py       # Cleanup service
│   └── autovision_client.py   # Supabase integration
├── frontend/                  # React frontend
│   ├── .env.example            # Frontend env template (copy to .env)
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── pages/
│   │   ├── contexts/
│   │   └── lib/
│   └── public/
└── supabase/                  # Database setup
    ├── schema.sql             # Canonical, idempotent schema (source of truth)
    └── deprecated/            # Superseded setup scripts, kept for reference only
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Commit your changes: `git commit -m 'Add amazing feature'`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

### Code Style

- **Python**: Follow PEP 8, use `black` for formatting
- **TypeScript**: Use Prettier and ESLint configurations
- **Commits**: Use conventional commit messages

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Common Issues

1. **Supabase Connection Issues**:

   - Verify your environment variables
   - Check Supabase project status
   - Re-run `supabase/schema.sql` (idempotent) to reconcile any schema drift

2. **Video Upload Failures**:

   - Ensure Supabase Storage bucket exists
   - Check file size limits (max 100MB)
   - Verify authentication tokens

3. **AI Model Errors**:
   - Install all required dependencies
   - Check GPU/CPU compatibility
   - Review model loading logs
