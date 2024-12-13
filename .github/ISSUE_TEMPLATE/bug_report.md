---
name: Bug Report
about: Create a detailed bug report to help us improve the API service
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description
### Summary
<!-- Provide a clear and concise description of the bug (minimum 50 characters) -->

### Expected Behavior
<!-- Describe what should happen -->

### Actual Behavior
<!-- Describe what actually happens -->

## System Context
### Affected Components
<!-- Check all that apply -->
- [ ] API Gateway (NGINX)
- [ ] Authentication Service
- [ ] API Service (Flask)
- [ ] Cache Layer (Redis)
- [ ] Database (PostgreSQL)
- [ ] Project Management
- [ ] Specification Management
- [ ] Item Management
- [ ] Google Cloud User Store
- [ ] Monitoring System

### Environment
<!-- Select the environment where the bug occurs -->
- [ ] Production (GCP)
- [ ] Staging (GCP)
- [ ] Development (Local/Cloud)

### Version
<!-- Specify the API version or commit hash -->
Version: 

## Reproduction Steps
### Prerequisites
<!-- List any required setup, authentication tokens, or test data -->

### Steps to Reproduce
1. 
2. 
3. 

### Reproduction Rate
<!-- Select one -->
- [ ] Always (100%)
- [ ] Frequently (>75%)
- [ ] Sometimes (25-75%)
- [ ] Rarely (<25%)

## Technical Details
### Error Logs
```
<!-- Insert relevant error logs, stack traces here -->
```

### Request Details
```
<!-- Insert API request/response details, headers, payload, response codes -->
```

### Performance Metrics
```
<!-- Insert response times, resource utilization, or other relevant metrics -->
```

## Impact Assessment
### Severity
<!-- Select one -->
- [ ] Critical (System Unavailable)
- [ ] High (Major Function Impaired)
- [ ] Medium (Function Degraded)
- [ ] Low (Minor Issue)

### Affected Users
<!-- Describe scope of impact (specific users, roles, or percentage of user base) -->

### Workaround
<!-- Describe any temporary solution or mitigation steps if available -->

## Additional Context
### Screenshots
<!-- Attach error messages, logs, or relevant system state screenshots -->

### Additional Notes
<!-- Add any other context about the problem here -->

<!-- 
This bug report template is integrated with:
- CI/CD pipeline for automated issue tracking
- Project board for workflow management
- Notification system for relevant stakeholders
- Automated triage system based on severity and components
-->