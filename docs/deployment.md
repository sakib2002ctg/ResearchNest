# Deployment Guide

## Overview

This document explains how ResearchNest is deployed and configured for local development and production-ready environments.

---

# Deployment Architecture

```text
                Client
                   │
                   ▼
             FastAPI Backend
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
 PostgreSQL Database      arXiv API
```

---

# Docker

Build and start all services:

```bash
docker compose up --build
```

Run in detached mode:

```bash
docker compose up -d
```

Stop all services:

```bash
docker compose down
```

Remove containers, networks, and volumes:

```bash
docker compose down -v
```

---

# Environment Files

ResearchNest uses multiple environment files.

| File | Purpose |
|------|---------|
| `.env.example` | Template configuration |
| `.env` | Local development |
| `.env.docker` | Docker configuration |

Never commit sensitive credentials to version control.

---

# Database Migration

Run Alembic migrations:

```bash
alembic upgrade head
```

---

# Health Checks

The Docker Compose configuration includes health checks to verify PostgreSQL availability before the backend starts.

---

# Continuous Integration

GitHub Actions automatically performs:

- Ruff linting
- Black formatting
- Test execution
- Coverage reporting

Every push and pull request is validated automatically.

---

# Production Considerations

Before deploying to production:

- Use a production ASGI server (for example, Gunicorn with Uvicorn workers).
- Store secrets securely using environment variables or a secret manager.
- Enable HTTPS.
- Configure database backups.
- Monitor application logs and metrics.

---

# Future Improvements

Planned deployment enhancements:

- Async FastAPI
- Redis
- Nginx reverse proxy
- Kubernetes deployment
- Terraform infrastructure
- Monitoring with Prometheus and Grafana