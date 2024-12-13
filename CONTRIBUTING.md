# Contributing to Specification Management API

## Table of Contents
- [Introduction](#introduction)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Security Guidelines](#security-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

## Introduction

### Project Overview
This project is a Flask-based REST API backend service designed to manage hierarchical specifications within user-owned projects. The system provides a secure and scalable foundation for specification management with Google Cloud User Store authentication and PostgreSQL storage.

### Code of Conduct
We are committed to providing a welcoming and inclusive environment. All contributors must:
- Use welcoming and inclusive language
- Be respectful of differing viewpoints
- Accept constructive criticism gracefully
- Focus on what's best for the community
- Show empathy towards other community members

### Getting Started
Before contributing, ensure you understand:
- The two-level specification hierarchy design
- REST API architecture principles
- Google Cloud User Store authentication flow
- PostgreSQL database operations
- Redis caching implementation

## Development Setup

### Prerequisites
- Python 3.8+
- Poetry 1.0+
- Docker and Docker Compose
- Git
- PostgreSQL 14+ (via Docker)
- Redis 6+ (via Docker)

### Environment Setup
1. Fork and clone the repository:
```bash
git clone https://github.com/your-username/specification-api.git
cd specification-api
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Unix
.\venv\Scripts\activate   # Windows
```

3. Install dependencies using Poetry:
```bash
poetry install
```

4. Start required services:
```bash
docker-compose up -d postgres redis
```

5. Configure local environment:
```bash
cp .env.example .env
# Edit .env with your local configuration
```

### IDE Setup
Recommended VS Code extensions:
- Python
- Python Test Explorer
- Python Docstring Generator
- GitLens
- Docker

## Development Workflow

### Branch Strategy
1. Create feature branches from `main`:
```bash
git checkout -b feature/description
git checkout -b bugfix/description
```

2. Branch naming conventions:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `hotfix/` - Critical fixes
- `docs/` - Documentation updates
- `test/` - Test additions/modifications

### Local Development
1. Ensure all services are running:
```bash
docker-compose ps
```

2. Run development server:
```bash
flask run --debug
```

3. Access API at `http://localhost:5000`

## Code Standards

### Code Formatting
We use Black 22.0+ with default configuration:
```bash
black .
```

### Code Linting
Pylint 2.0+ with custom rules:
```bash
pylint src tests
```

### Documentation
- All modules must have docstrings
- All public functions/methods require docstrings
- Complex logic needs inline comments
- API endpoints must include OpenAPI documentation

### Type Hints
- Use type hints for all function parameters and return values
- Use `typing` module for complex types
- Validate with `mypy`

## Testing Requirements

### Test Coverage
Minimum requirements:
- Unit test coverage: 80%
- Integration test coverage: 70%
- API endpoint coverage: 100%

### Running Tests
```bash
# Unit tests
pytest tests/unit

# Integration tests
pytest tests/integration

# Coverage report
pytest --cov=src tests/
```

### Test Documentation
Each test file must include:
- Purpose of test suite
- Test case descriptions
- Mock/fixture explanations
- Expected outcomes

## Security Guidelines

### Authentication Implementation
- Use Google Cloud User Store OAuth 2.0
- Implement JWT token validation
- Cache validation results
- Handle token expiration

### Authorization Controls
- Implement project ownership validation
- Apply rate limiting (1000 req/hour/user)
- Prevent brute force attacks
- Use row-level security in PostgreSQL

### Data Protection
- Use TLS 1.3 for all connections
- Encrypt sensitive data at rest
- Implement input sanitization
- Use parameterized SQL queries

### Dependency Security
- Regular dependency updates
- Security vulnerability scanning
- License compliance checks
- Container image scanning

## Pull Request Process

### PR Requirements
1. Complete PR template with:
- Change description
- Testing details
- Security considerations
- Documentation updates

2. Pass all checks:
- CI pipeline success
- Code coverage thresholds
- Security scan results
- Documentation completeness

### Review Process
1. Two approvals required
2. All comments addressed
3. CI/CD pipeline passed
4. Documentation updated

### Merge Criteria
- Clean commit history
- Passing CI/CD pipeline
- Approved reviews
- Up-to-date branch

## Issue Reporting

### Bug Reports
Use the bug report template including:
- Clear description
- Reproduction steps
- Expected behavior
- System context
- Logs/screenshots

### Feature Requests
Include:
- Use case description
- Proposed solution
- Alternative approaches
- Implementation considerations

### Response Times
- Critical bugs: 24 hours
- Major bugs: 48 hours
- Feature requests: 1 week
- General issues: 1 week

## Questions and Support
- Create a discussion for questions
- Join our Slack channel
- Check existing documentation
- Review closed issues

Thank you for contributing to the Specification Management API project!