# Azure AI Foundry KYC Orchestrator

A comprehensive KYC (Know Your Customer) orchestrator that uses Azure AI Foundry agents to streamline insurance customer onboarding.

## Features

- **AI-Powered Workflow**: Multiple Azure AI agents handle different stages of the KYC process
- **Real-time Chat Interface**: Interactive chat system for customer support
- **Step-by-Step Progress**: Visual workflow tracking with real-time updates
- **Secure Authentication**: Azure API key management with secure storage
- **Responsive Design**: Modern React frontend with Material-UI components
- **Health Monitoring**: Built-in health checks for all services

## Architecture

### Backend (FastAPI)
- **main.py**: Core orchestrator with REST API endpoints
- **Azure OpenAI Integration**: Intelligent responses and decision making
- **Session Management**: Stateful KYC workflow tracking
- **Error Handling**: Comprehensive error handling and retry logic

### Frontend (React + TypeScript)
- **Modern UI**: Material-UI components with responsive design
- **Real-time Updates**: Live session status and chat updates
- **Workflow Visualization**: Step-by-step progress tracking
- **Secure API Management**: Local storage for API keys

### Azure AI Agents
1. **Intake Agent**: Customer information collection
2. **Verification Agent**: Identity and document verification
3. **Eligibility Agent**: Insurance eligibility assessment
4. **Recommendation Agent**: Product recommendation engine
5. **Compliance Agent**: Regulatory compliance checking
6. **Action Agent**: Final processing and onboarding

## Prerequisites

- Python 3.8+
- Node.js 16+
- Azure OpenAI service account
- Azure AI Foundry access (optional for full agent functionality)

## Installation

### Backend Setup

1. **Clone and navigate to the project**:
   ```bash
   cd AzureAiFoundryBasicAgentOrchestration
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Update the `.env` file with your Azure credentials:
   ```env
   AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-api-key-here
   AZURE_OPENAI_DEPLOYMENT_NAME=gpt-35-turbo
   ```

5. **Start the backend server**:
   ```bash
   python main.py
   ```
   The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```
   The frontend will be available at `http://localhost:3000`

## Usage

1. **Start both servers** (backend on port 8000, frontend on port 3000)

2. **Open the application** at `http://localhost:3000`

3. **Configure API Key**: On first visit, you'll be prompted to enter your Azure API key

4. **Start KYC Process**:
   - Fill in customer information on the welcome page
   - Click "Start KYC Process"
   - Follow the guided workflow steps
   - Use the chat interface for questions and additional information

5. **Monitor Progress**: Track workflow progress in the sidebar and receive real-time updates

## API Endpoints

### Core Endpoints
- `GET /` - Health check
- `POST /start-session` - Start new KYC session
- `GET /session/{session_id}` - Get session details
- `POST /chat/{session_id}` - Send chat message
- `POST /run-step/{session_id}` - Execute workflow step
- `PUT /session/{session_id}` - Update session data
- `GET /steps` - Get workflow steps
- `GET /health` - Detailed health check

### Authentication
Most endpoints require an `api-key` header with your Azure API key.

## Configuration

### Environment Variables
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI service endpoint
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Deployment name for your model
- `AZURE_OPENAI_API_VERSION`: API version (default: 2024-10-21)

### Frontend Configuration
- `VITE_API_BASE_URL`: Backend API URL (default: http://localhost:8000)

## Development

### Backend Development
```bash
# Install development dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development
```bash
# Start development server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Production Deployment

### Backend Deployment
```bash
# Build Docker image
docker build -t kyc-orchestrator-backend .

# Run container
docker run -p 8000:8000 --env-file .env kyc-orchestrator-backend
```

### Frontend Deployment
```bash
# Build production bundle
npm run build

# Deploy dist/ folder to your hosting service
```

## Troubleshooting

### Common Issues

1. **Azure OpenAI Connection Issues**:
   - Verify your endpoint URL and API key
   - Check that your deployment name is correct
   - Ensure your Azure subscription has sufficient quota

2. **Frontend API Connection**:
   - Verify backend is running on port 8000
   - Check CORS settings in main.py
   - Ensure API key is properly configured

3. **Session Management**:
   - Sessions are stored in memory by default
   - For production, implement Redis or database storage
   - Check session timeout settings

### Health Checks
- Backend health: `GET http://localhost:8000/health`
- Frontend connectivity: Check browser console for errors

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section
- Review Azure OpenAI documentation
- Create an issue in the repository