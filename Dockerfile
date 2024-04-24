ARG FUNCTION_DIR="/function"
ARG MODEL_DIR

FROM python:3.10-slim as base

FROM base as builder

ENV AWS_LAMBDA_FUNCTION_TIMEOUT="900"
ENV TZ=Europe/Stockholm

ARG FUNCTION_DIR
ARG MODEL_DIR

WORKDIR /function

# Install Chromium, ChromeDriver, and system dependencies
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && apt-get update && apt-get install -y chromium chromium-driver \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && mkdir -p ${MODEL_DIR}

COPY modules/ ${FUNCTION_DIR}/modules/

# Remove when files are moved to external source?
COPY lambda_function.py ${FUNCTION_DIR}
COPY main.py ${FUNCTION_DIR}
COPY requirements.txt ${FUNCTION_DIR}

# Copy model
COPY temp_model/ ${MODEL_DIR}

# RUN ls -R

# Install the function's dependencies including awslambdaric
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r ${FUNCTION_DIR}/requirements.txt \
    && pip install --no-cache-dir awslambdaric

FROM base as final

ARG FUNCTION_DIR
ARG MODEL_DIR

ENV AWS_LAMBDA_FUNCTION_TIMEOUT="900"
ENV TZ=Europe/Stockholm

# Install Chromium, ChromeDriver, and system dependencies, then clean up
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && apt-get update \
    && apt-get install -y chromium chromium-driver \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /function
COPY --from=builder ${FUNCTION_DIR} ${FUNCTION_DIR}
COPY --from=builder ${MODEL_DIR} ${MODEL_DIR}
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set runtime interface client as default command for the container runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]

# Pass the name of the function handler as an argument to the runtime
CMD [ "lambda_function.bot_handler" ]