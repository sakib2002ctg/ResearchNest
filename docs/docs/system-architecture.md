# ResearchNest System Architecture

## Components

- React Frontend
- FastAPI Backend
- PostgreSQL Database
- ChromaDB Vector Database
- AI Service (Hugging Face Models)

## Request Flow

1. User interacts with the frontend.
2. Frontend sends an HTTP request to the backend.
3. Backend processes the request.
4. Backend queries PostgreSQL or ChromaDB as needed.
5. Backend calls the AI service when AI functionality is required.
6. Backend returns the response to the frontend.
7. Frontend displays the result to the user.

## Design Principles

- Separation of concerns
- Scalable architecture
- Secure communication through the backend
- Modular services