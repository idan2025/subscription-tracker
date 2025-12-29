# Subscription Tracker

A self-hosted web application for managing and tracking recurring subscriptions. Monitor costs, receive renewal alerts, and analyze spending patterns.

## Features

### Core Features
- User authentication and account management
- Dashboard with monthly and yearly cost summaries
- Subscription CRUD operations (Create, Read, Update, Delete)
- Automated renewal alerts (7-day advance notice)
- Category-based spending analytics
- Multi-user support with admin roles
- Admin panel for system configuration
- Dark mode with light mode option (theme persists across sessions)

### AI-Powered Features (Optional)
- **Smart Alternatives Finder**: AI searches for cheaper subscription alternatives
- **AI Chat Assistant**: Conversational interface for subscription queries and optimization
- **Spending Analysis**: AI-powered insights on spending patterns and trends
- **Personalized Recommendations**: Tailored suggestions for cost reduction and optimization
- **Multi-Provider Support**:
  - Anthropic Claude (API)
  - OpenAI GPT (API)
  - Ollama (Self-hosted, local AI)
- **Privacy-First**: AI features can be completely disabled; app works fully offline without AI

## Technology Stack

- **Backend**: Python 3.11, Flask
- **Database**: MySQL 8.0
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **AI Integration**: Anthropic SDK, OpenAI SDK, Ollama API
- **Deployment**: Docker, Kubernetes, Helm
- **UI/UX**: Dark mode by default, responsive design

## Installation

### Prerequisites

- Docker and Docker Compose, OR
- Kubernetes cluster with kubectl and Helm 3.x, OR
- Python 3.11+ with pip

### Method 1: Docker Compose

```bash
# Clone the repository
git clone https://github.com/idan2025/subscription-tracker.git
cd subscription-tracker

# Start services
docker-compose up -d

# Access the application
# http://localhost:5000
```

### Method 2: Kubernetes with Helm

```bash
# Clone the repository
git clone https://github.com/idan2025/subscription-tracker.git
cd subscription-tracker

# Install with Helm
helm install subscription-tracker ./helm-charts/subscription-tracker \
  --namespace subscription-tracker \
  --create-namespace

# Get the service endpoint
kubectl get svc -n subscription-tracker
```

### Method 3: Kubernetes with Manifests

```bash
# Apply base manifests
kubectl apply -f k8s-manifests/base/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=flask-app -n subscription-tracker --timeout=300s

# Get the service endpoint
kubectl get svc -n subscription-tracker
```

### Method 4: Manual Installation

```bash
# Install dependencies
pip install -r app/requirements.txt

# Set environment variables
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=your_password
export DB_NAME=subscription_tracker
export SECRET_KEY=your_secret_key

# Run the application
python app/app.py
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | MySQL server hostname | localhost |
| `DB_PORT` | MySQL server port | 3306 |
| `DB_USER` | Database username | root |
| `DB_PASSWORD` | Database password | rootpassword |
| `DB_NAME` | Database name | subscription_tracker |
| `SECRET_KEY` | Flask session secret key | Auto-generated |
| `FLASK_ENV` | Application environment | production |

### Database Setup

The application automatically creates required tables on first run. Manual schema initialization:

```bash
# Connect to MySQL
mysql -u root -p

# Create database
CREATE DATABASE subscription_tracker;

# Tables are created automatically by the application
```


## Usage

### Initial Setup

1. Navigate to the application URL
2. Create the first admin account through the setup wizard
3. Log in with your credentials
4. Start adding subscriptions from the dashboard

### Adding Subscriptions

1. Click "Add Subscription" from the dashboard
2. Enter subscription details:
   - Name
   - Cost
   - Billing cycle (weekly/monthly/yearly)
   - Next renewal date
   - Category
3. Save the subscription

### Managing Subscriptions

- **Edit**: Click on any subscription to modify details
- **Delete**: Remove subscriptions you no longer need
- **View Analytics**: Dashboard shows cost breakdowns by category
- **Renewal Alerts**: Automatic notifications 7 days before renewal

### Admin Functions

Admin users can:
- Access the admin panel
- Configure AI features and providers
- Enable/disable individual AI features
- Test AI provider connections
- Manage application configuration
- Promote users to admin status (via database)

### AI Configuration

To enable AI features:

1. Log in as an admin user
2. Navigate to the Admin Panel
3. Enable AI Features toggle
4. Select your AI provider:
   - **Claude (Anthropic)**: Requires API key from [console.anthropic.com](https://console.anthropic.com)
   - **OpenAI**: Requires API key from [platform.openai.com](https://platform.openai.com)
   - **Ollama**: Self-hosted option, requires local Ollama server
5. Enter your API credentials
6. Test the connection
7. Enable desired features:
   - Smart Alternatives Finder
   - AI Chat Assistant
   - Spending Analysis
   - Personalized Recommendations
8. Save settings

**Privacy Note**: When AI is disabled, the application functions as a standard subscription tracker with no external API calls.

## Deployment Options

### Docker Compose

Suitable for single-server deployments. Includes MySQL and the Flask application.

### Kubernetes

Production-ready deployment with:
- StatefulSet for MySQL with persistent storage
- Deployment for Flask application with multiple replicas
- LoadBalancer service for external access
- Horizontal Pod Autoscaling support
- Health checks and readiness probes

### Helm Chart

Parameterized deployment with:
- Configurable resource limits
- Multiple environment overlays (dev/prod)
- Secrets management
- Ingress configuration
- Optional monitoring integration

## Security Considerations

### Production Deployment

- Change all default passwords
- Use strong, randomly generated SECRET_KEY
- Enable HTTPS/TLS for external access
- Implement network policies in Kubernetes
- Regular security updates for base images
- Store sensitive credentials in secrets management systems
- Use environment variables or Kubernetes secrets for database credentials
- Enable MySQL SSL/TLS connections in production

### AI Security

- **API Key Storage**: AI provider API keys are encrypted before storage in the database
- **Access Control**: Only admin users can configure AI settings
- **Feature Isolation**: AI features can be individually enabled/disabled
- **Privacy Mode**: Complete AI disable option for offline/air-gapped deployments
- **Self-Hosted Option**: Ollama support allows fully local AI without external API calls
- **No Data Sharing**: User subscription data never leaves your infrastructure (unless using cloud AI providers)

## Troubleshooting

### Database Connection Errors

```bash
# Verify MySQL is running
docker ps | grep mysql

# Test database connection
mysql -h localhost -u root -p subscription_tracker

# Check application logs
docker logs subscription-tracker
kubectl logs -l app=flask-app -n subscription-tracker
```

### Application Not Starting

Common issues:
- MySQL not ready (wait 10-30 seconds after starting)
- Incorrect database credentials
- Port conflicts (default: 5000)

Check logs for detailed error messages:
```bash
docker logs subscription-tracker
kubectl logs -l app=flask-app -n subscription-tracker
```

### Pod Issues in Kubernetes

```bash
# Check pod status
kubectl get pods -n subscription-tracker

# Check pod logs
kubectl logs -l app=flask-app -n subscription-tracker

# Describe pod for events
kubectl describe pod -l app=flask-app -n subscription-tracker
```

### AI Features Issues

**AI Features Not Appearing**
- Verify AI is enabled in Admin Panel
- Check that specific feature flags are enabled
- Ensure API key is configured correctly
- Test the AI connection using the "Test Connection" button

**API Connection Failures**
- **Claude/OpenAI**: Verify API key is valid and has credits
- **Ollama**: Ensure Ollama server is running and accessible
- Check application logs for detailed error messages
- Verify network connectivity to API endpoints

**Ollama-Specific Issues**
```bash
# Check Ollama server status
curl http://localhost:11434/api/tags

# Pull a model if needed
ollama pull llama3.2

# Check available models in admin panel
# Use "Fetch Models" button to see all installed models
```

## Development

### Project Structure

```
subscription-tracker/
├── app/
│   ├── app.py              # Main application
│   ├── ai_providers.py     # AI provider abstraction layer
│   ├── ai_services.py      # AI business logic
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile          # Container image
│   └── templates/          # HTML templates
│       ├── dashboard.html  # Main dashboard with AI features
│       ├── admin.html      # Admin panel with AI configuration
│       ├── login.html      # Login page
│       ├── register.html   # Registration page
│       └── setup.html      # Initial setup wizard
├── k8s-manifests/
│   ├── base/               # Base Kubernetes resources
│   └── overlays/           # Environment-specific configs
├── helm-charts/
│   └── subscription-tracker/  # Helm chart
├── docker-compose.yml      # Docker Compose config
└── README.md
```

### Building Custom Images

```bash
# Build Docker image
docker build -t your-registry/subscription-tracker:tag ./app

# Push to registry
docker push your-registry/subscription-tracker:tag

# Update deployment
kubectl set image deployment/flask-app flask-app=your-registry/subscription-tracker:tag -n subscription-tracker
```

### Local Development

```bash
# Install dependencies
pip install -r app/requirements.txt

# Set up local MySQL
docker run -d -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=rootpassword \
  -e MYSQL_DATABASE=subscription_tracker \
  mysql:8.0

# Run application
export DB_HOST=localhost
export DB_PASSWORD=rootpassword
python app/app.py
```

## Contributing

Contributions are welcome. Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Support

- Report issues: https://github.com/idan2025/subscription-tracker/issues
- Discussions: https://github.com/idan2025/subscription-tracker/discussions
