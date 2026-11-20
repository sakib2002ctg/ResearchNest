FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 tesseract-ocr tesseract-ocr-ben \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 researchnest \
    && useradd --uid 10001 --gid researchnest --create-home researchnest \
    && install -d -o researchnest -g researchnest -m 700 \
       /var/lib/researchnest/pdfs /var/lib/researchnest/assets
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=researchnest:researchnest . .
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
