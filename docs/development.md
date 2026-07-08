# Development Guide

## Overview

This guide explains how to set up a local development environment for ResearchNest.

---

# Prerequisites

Install the following software before getting started:

- Python 3.13+
- Git
- Docker Desktop
- PostgreSQL (optional when using Docker)

---

# Clone the Repository

```bash
git clone <repository-url>
cd ResearchNest
```

---

# Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Copy the example configuration:

```bash
cp .env.example .env
```

Update the values according to your local environment.

---

# Database Migration

Run Alembic migrations:

```bash
alembic upgrade head
```

---

# Run the Application

Start the FastAPI development server:

```bash
uvicorn app.main:app --reload
```

Application:

```
http://localhost:8000
```

Swagger:

```
http://localhost:8000/docs
```

ReDoc:

```
http://localhost:8000/redoc
```

---

# Docker Development

Start the application:

```bash
docker compose up --build
```

Stop the application:

```bash
docker compose down
```

---

# Running Tests

Run all tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

---

# Code Quality

Run Ruff:

```bash
ruff check .
```

Run Black:

```bash
black .
```

Run pre-commit manually:

```bash
pre-commit run --all-files
```

---

# Git Workflow

Create a feature branch:

```bash
git checkout -b feature/my-feature
```

Commit changes:

```bash
git commit -m "feat: add awesome feature"
```

Push changes:

```bash
git push origin feature/my-feature
```

---

# Project Structure

```
Router
    ↓
Service
    ↓
Repository
    ↓
Database
```

---

# Best Practices

- Follow Clean Architecture.
- Keep routers thin.
- Place business logic in services.
- Keep repositories focused on data access.
- Write tests for new features.
- Run Ruff, Black, and Pytest before committing.
- Keep commits small and descriptive.

---

# Need Help?

If you encounter an issue:

1. Check the project documentation.
2. Review the GitHub Issues.
3. Create a new issue if the problem persists.