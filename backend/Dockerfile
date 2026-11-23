FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Utilisateur applicatif + dossier des fichiers bruts accessible
# (le volume fichierdata hérite de ce propriétaire à sa création)
RUN useradd --create-home ncshift \
    && mkdir -p /data \
    && chown -R ncshift /srv /data
USER ncshift

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]