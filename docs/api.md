# API Documentation

## Overview

ResearchNest exposes a RESTful API built with FastAPI.

Interactive API documentation is automatically generated.

| Documentation | URL |
|---------------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

---

# Authentication

ResearchNest uses **JWT Bearer Authentication**.

Protected endpoints require the following HTTP header:

```http
Authorization: Bearer <access_token>
```

---

# Authentication Endpoints

## Login

| Method | Endpoint |
|----------|----------|
| POST | `/auth/login` |

Authenticate a user and receive a JWT access token.

---

# Paper Endpoints

## Get All Papers

| Method | Endpoint |
|----------|----------|
| GET | `/papers` |

Returns all papers owned by the authenticated user.

Authentication:

✅ Required

---

## Create Paper

| Method | Endpoint |
|----------|----------|
| POST | `/papers` |

Create a new paper.

Authentication:

✅ Required

---

## Get Paper

| Method | Endpoint |
|----------|----------|
| GET | `/papers/{paper_id}` |

Retrieve a paper by its ID.

Authentication:

✅ Required

---

## Update Paper

| Method | Endpoint |
|----------|----------|
| PUT | `/papers/{paper_id}` |

Update an existing paper.

Authentication:

✅ Required

---

## Delete Paper

| Method | Endpoint |
|----------|----------|
| DELETE | `/papers/{paper_id}` |

Delete a paper.

Authentication:

✅ Required

---

# Search Endpoints

## Search Papers

| Method | Endpoint |
|----------|----------|
| GET | `/papers/search` |

Search papers with pagination.

Authentication:

✅ Required

---

# External Research

## Search arXiv

| Method | Endpoint |
|----------|----------|
| GET | `/research/search` |

Search research papers using the arXiv API.

Authentication:

❌ Not Required

---

# Response Format

Successful responses generally follow:

```json
{
  "data": {},
  "message": "Success"
}
```

Validation errors follow FastAPI's standard error format.

---

# HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

---

# Version

Current API Version:

**v1.4.0**