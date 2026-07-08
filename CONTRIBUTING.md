# Contributing

Thank you for considering contributing to ResearchNest!

## Development Setup

1. Fork the repository.
2. Clone your fork.
3. Create a feature branch.

```bash
git checkout -b feature/your-feature
```

4. Install dependencies.

```bash
pip install -r requirements.txt
```

5. Run the application.

```bash
docker compose up --build
```

6. Run quality checks.

```bash
ruff check .
black .
pytest
```

7. Commit your changes.

```bash
git commit -m "feat: add awesome feature"
```

8. Push your branch and open a Pull Request.

## Coding Standards

- Follow Clean Architecture.
- Use dependency injection.
- Write tests for new features.
- Keep code formatted with Black.
- Ensure Ruff passes before committing.