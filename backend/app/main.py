from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from app.database.database import engine, Base
from app.models.research_paper import ResearchPaper
from app.routers.research import router as research_router
from app.routers.papers import router as papers_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Test database connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        # Create all tables
        Base.metadata.create_all(bind=engine)

        print("✅ Connected to PostgreSQL successfully!")
        print("✅ Database tables created!")

    except Exception as e:
        print("❌ Database connection failed!")
        print(e)

    yield


app = FastAPI(
    title="ResearchNest API",
    version="1.0.0",
    lifespan=lifespan
)

# Routers
app.include_router(research_router)
app.include_router(papers_router)


class Student(BaseModel):
    name: str
    age: int


@app.get("/")
def home():
    return {
        "message": "Welcome to ResearchNest!"
    }


@app.get("/health")
def health():
    return {
        "status": "OK"
    }


@app.get("/about")
def about():
    return {
        "project": "ResearchNest",
        "version": "1.0"
    }


@app.get("/greet/{name}")
def greet(name: str):
    return {
        "message": f"Hello {name}"
    }


@app.get("/add")
def add(a: int, b: int):
    return {
        "result": a + b
    }


@app.post("/student")
def create_student(student: Student):
    return {
        "message": "Student created successfully!",
        "student": student
    }