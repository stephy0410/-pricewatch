FROM public.ecr.aws/lambda/python:3.12

# Instalar dependencias del sistema necesarias para curl_cffi
RUN dnf install -y \
    gcc \
    libcurl-devel \
    openssl-devel \
    python3-devel \
    && dnf clean all

# Copiar requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Instalar dependencias Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Variables de entorno
ENV PYTHONUNBUFFERED=1

CMD ["lambda_function.lambda_handler"]