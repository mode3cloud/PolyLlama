FROM openresty/openresty:alpine

# Install additional packages needed
RUN apk add --no-cache curl jq

# Install lua-resty-http module
RUN apk add --no-cache git \
    && cd /tmp \
    && git clone https://github.com/ledgetech/lua-resty-http.git \
    && cd lua-resty-http \
    && cp -r lib/resty/* /usr/local/openresty/lualib/resty/ \
    && rm -rf /tmp/lua-resty-http

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Create UI directory
RUN mkdir -p /usr/share/nginx/html/ui

# Copy proxy parameters file
COPY proxy_params.conf /etc/nginx/proxy_params.conf

# Expose port
EXPOSE 11434