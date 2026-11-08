FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
RUN pip install .

# Nunca rodar a aplicação como root dentro do container.
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000

# Migrations antes de subir: o schema sempre corresponde à versão do código.
CMD ["sh", "-c", "alembic upgrade head && uvicorn stock.main:create_app --factory --host 0.0.0.0 --port 8000"]
