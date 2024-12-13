# Specification Management API Backend

## Overview

A production-ready REST API backend system built with Flask/Python for managing hierarchical specifications within user-owned projects. The system provides secure, scalable specification management with Google Cloud User Store authentication and PostgreSQL persistence.

### Key Features

- User authentication via Google Cloud User Store
- Project-based specification management
- Two-level hierarchical organization
- Robust access control and data security
- High-performance caching with Redis
- Containerized deployment with Docker

## Prerequisites

### Required Software

- Python 3.8+
- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 14+
- Redis 6+
- Google Cloud SDK 400.0+

### Cloud Platform Setup

1. Google Cloud Platform account with:
   - Cloud User Store enabled
   - Cloud SQL instance (PostgreSQL 14+)
   - Cloud Memorystore (Redis) instance
   - Cloud Run service account

### Development Tools

- Poetry 1.0+ (Dependency management)
- Git 2.0+
- Visual Studio Code (recommended) or PyCharm

## Development Setup

### Local Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/organization/project
cd src/backend
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration values
```

3. Install dependencies:
```bash
poetry install
```

4. Initialize database:
```bash
poetry run flask db upgrade
```

5. Start development server:
```bash
poetry run flask run
```

### Docker Development Environment

1. Build and start services:
```bash
docker-compose build
docker-compose up -d
```

2. Initialize database:
```bash
docker-compose exec api flask db upgrade
```

3. Verify health:
```bash
docker-compose exec api flask check-health
```

## Project Structure

```
src/backend/
├── app/                    # Application package
│   ├── api/               # API endpoints
│   ├── auth/              # Authentication
│   ├── models/            # Database models
│   ├── schemas/           # Data serialization
│   └── services/          # Business logic
├── tests/                 # Test suite
├── migrations/            # Database migrations
├── docker/                # Docker configurations
├── .env.example          # Environment template
├── docker-compose.yml    # Development services
├── Dockerfile            # Production container
└── pyproject.toml        # Project dependencies
```

## API Documentation

### Authentication

All endpoints require authentication via Google OAuth 2.0. Include the Bearer token in the Authorization header:

```
Authorization: Bearer <token>
```

### Core Endpoints

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| /api/v1/projects | GET | List user projects | Required |
| /api/v1/specifications/{id} | DELETE | Delete specification | Required |
| /api/v1/specifications/{id}/items | GET | List items | Required |

Detailed API documentation is available at `/api/docs` when running in development mode.

## Testing

### Running Tests

1. Unit tests:
```bash
poetry run pytest
```

2. Coverage report:
```bash
poetry run pytest --cov=app tests/
```

3. Code style:
```bash
poetry run black .
poetry run pylint app/
```

## Deployment

### Production Deployment (Google Cloud Run)

1. Authenticate with Google Cloud:
```bash
gcloud auth configure-docker
```

2. Build and push container:
```bash
docker build -t gcr.io/project-id/api:version .
docker push gcr.io/project-id/api:version
```

3. Deploy to Cloud Run:
```bash
gcloud run deploy api-service \
  --image gcr.io/project-id/api:version \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Environment Variables

Required environment variables (see `.env.example`):

- `FLASK_APP`: Application entry point
- `FLASK_ENV`: Environment (development/production)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `GOOGLE_CLIENT_ID`: OAuth 2.0 client ID
- `GOOGLE_CLIENT_SECRET`: OAuth 2.0 client secret
- `JWT_SECRET_KEY`: JWT signing key

## Security

### Authentication Flow

1. Client authenticates with Google
2. Exchange OAuth token for JWT
3. Use JWT for API requests
4. Token validation and user context

### Data Protection

- TLS 1.3 for all connections
- AES-256 database column encryption
- JWT token encryption (HS256)
- Rate limiting: 1000 requests/hour/user
- SQL injection protection via SQLAlchemy
- XSS protection headers

## Maintenance

### Health Monitoring

- `/health` endpoint for service health
- Prometheus metrics at `/metrics`
- Structured logging to stdout
- Error tracking via Sentry

### Backup Procedures

1. Database backups:
   - Daily full backups
   - Point-in-time recovery enabled
   - 7-day retention period

2. Configuration backups:
   - Version controlled
   - Encrypted secrets management
   - Regular audit and rotation

### Performance Optimization

- Connection pooling via PgBouncer
- Redis caching for frequent queries
- Query optimization via indexes
- Regular performance monitoring

## Support

- Technical Issues: Create GitHub issue
- Security Concerns: security@organization.com
- Documentation: See `/api/docs`

## License

Proprietary - All rights reserved

---
Last Updated: 2024
Version: 1.0.0
Maintainers: Development Team