# SAKSHYA backend — local FastAPI + SQLite + PQC. No external services.
# Build context is the repository root (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    # MUST-6: fail the BUILD (not the demo) unless real ML-KEM-768 / ML-DSA-65 is present.
    && python -c "import cryptography; assert cryptography.__version__ == '50.0.0', cryptography.__version__; \
from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey; \
from cryptography.hazmat.primitives.asymmetric.mldsa import MLDSA65PrivateKey; print('PQC OK', cryptography.__version__)"

# Application factory entry-point (app.py) + executable (main.py) + package.
COPY backend/app.py backend/main.py ./
COPY backend/app ./app

# Storage is a mounted volume in docker-compose so evidence survives rebuilds.
RUN mkdir -p /app/storage

EXPOSE 8100

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]
