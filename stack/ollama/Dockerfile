FROM ollama/ollama:latest

USER root
WORKDIR /root

ENV DEBIAN_FRONTEND=noninteractive

# Install deps including build tools
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    nano \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV DEBIAN_FRONTEND=

# # ----- CUDA Malloc Host Shim -----
# COPY cuda_host_shim.cpp /root/cuda_host_shim.cpp

# RUN g++ -shared -fPIC -o /usr/local/lib/libcudahostshim.so /root/cuda_host_shim.cpp

# # Preload shim to override cudaMallocHost globally
# ENV LD_PRELOAD=/usr/local/lib/libcudahostshim.so

# ----- NGINX Config -----
COPY startServices.sh /root/startServices.sh
RUN chmod +x /root/startServices.sh

# Copy GPU metrics server
COPY gpu_metrics_server.py /root/gpu_metrics_server.py
RUN chmod +x /root/gpu_metrics_server.py

EXPOSE 11434 11435

ENTRYPOINT ["/root/startServices.sh"]
