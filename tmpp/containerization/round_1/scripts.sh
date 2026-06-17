docker run --name chroma \
  -p 8001:8000 \
  -v chroma_data:/data \
  -e IS_PERSISTENT=TRUE \
  -e PERSIST_DIRECTORY=/data \
  -e ANONYMIZED_TELEMETRY=FALSE \
  chromadb/chroma:1.0.15

# -v creates a volume named chroma_data and mounts it to /data in the container. This allows the Chroma-DB to persist data even if the container is stopped or removed.