### 📄 infra/caddy/Caddyfile

**Größe:** 789 B | **md5:** `3bfda9b8da56d21a02514d98eb48fd0a`

```plaintext
{
  auto_https off
  servers :8081 {
    protocol {
      experimental_http3
    }
    logs {
      level INFO
    }
  }
}

:8081 {
  encode zstd gzip
  # Strippt /api Prefix, damit /api/health -> /health an der API ankommt
  handle_path /api/* {
    reverse_proxy api:8080
  }
  reverse_proxy /* web:5173
  header {
    # Dev-CSP: HMR/WebSocket & Dev-Assets erlauben; bei Bedarf später härten
    # Für externe Tiles ggf. ergänzen, z.B.:
    #   img-src 'self' data: blob: https://tile.openstreetmap.org https://*.tile.openstreetmap.org;
    Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:; img-src 'self' data: blob:; object-src 'none';"
    X-Frame-Options "DENY"
    Referrer-Policy "no-referrer"
  }
}
```

