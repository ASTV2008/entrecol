FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 10001 entrecol \
    && useradd --uid 10001 --gid entrecol --home-dir /home/entrecol \
        --create-home --shell /usr/sbin/nologin entrecol

COPY --chown=entrecol:entrecol backend/app ./app
COPY --chown=entrecol:entrecol frontend /frontend

USER entrecol:entrecol

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
