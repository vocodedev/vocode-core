# Use the official micromamba image as a base
FROM docker.io/mambaorg/micromamba:1.5-jammy

# Create a new user '$MAMBA_USER' and set the working directory
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.docker.yml /tmp/environment.yml

# Install the specified packages using micromamba
RUN micromamba install -y -n base -f /tmp/environment.yml && \
    micromamba clean --all --yes    

USER root
WORKDIR /usr/local/src

ARG VOCODE_USER=vocode
ARG VOCODE_UID=8476
ARG VOCODE_GID=8476

RUN groupadd --gid $VOCODE_GID $VOCODE_USER && \
    useradd --uid $VOCODE_UID --gid $VOCODE_GID --shell /bin/bash --create-home $VOCODE_USER

# COPY --chown=$VOCODE_USER:$VOCODE_USER ../../../ /vocode-python
# WORKDIR /usr/local/src/vocode
# RUN poetry install -E all

# Copy the rest of your application files into the Docker image
COPY --chown=$VOCODE_USER:$VOCODE_USER . /vocode
WORKDIR /vocode

#USER vocode
USER root

ENV DOCKER_ENV="docker"

# # Expose the port your FastAPI app will run on
EXPOSE 19002

# Set build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# Set labels
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="vocode" \
      org.label-schema.description="Vocode Docker Image" \
      org.label-schema.url="https://vocode.dev/" \
      org.label-schema.vcs-url="https://github.com/vocodedev" \
      org.label-schema.maintainer="seb@vocode.dev" \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.vendor="Vocode" \
      org.label-schema.version=$VERSION

# Start the FastAPI app using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "19002"]