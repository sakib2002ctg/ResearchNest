from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.logging import logger
from app.database.database import engine
from app.exceptions.handlers import register_exception_handlers
from app.middleware.logging import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Test database connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        logger.info("Connected to PostgreSQL successfully!")
        logger.info("ResearchNest application started.")

    except Exception:
        logger.exception("Database connection failed!")

    yield

    logger.info("ResearchNest application stopped.")


app = FastAPI(
    title="ResearchNest API",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(LoggingMiddleware)

# Register global exception handlers
register_exception_handlers(app)

# Versioned API
app.include_router(api_router)


# -------------------------------------------------------------------
# Temporary demo endpoints
# These will be removed in Cleanup Sprint Step 3.
# -------------------------------------------------------------------


class Student(BaseModel):
    name: str
    age: int


@app.get("/")
def home():
    return {"message": "Welcome to ResearchNest!"}


@app.get("/about")
def about():
    return {"project": "ResearchNest", "version": "1.0"}


@app.get("/greet/{name}")
def greet(name: str):
    return {"message": f"Hello {name}"}


@app.get("/add")
def add(a: int, b: int):
    return {"result": a + b}


@app.post("/student")
def create_student(student: Student):
    return {
        "message": "Student created successfully!",
        "student": student,
    }
