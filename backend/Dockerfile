FROM python:3.12-slim

# uvicorn/arq : pas de bash pour simplifier ; curl utile pour la sonde /healthz
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Pas de root applicatif
RUN useradd --create-home ncshift && chown -R ncshift /srv
USER ncshift

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
