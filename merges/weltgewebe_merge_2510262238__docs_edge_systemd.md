### 📄 docs/edge/systemd/README.md

**Größe:** 214 B | **md5:** `cead3a78ff4ddffd156fd97cde9b4061`

```markdown
# Edge systemd units (optional)

This is **not** the primary orchestration path. Default remains **Docker Compose → Nomad**.
Use these units only for tiny single-node edge installs where Compose isn't available.
```

### 📄 docs/edge/systemd/weltgewebe-projector.service

**Größe:** 490 B | **md5:** `59549cecea7d486a5ea6ce8db0907aab`

```plaintext
[Unit]
Description=Weltgewebe Projector (timeline/search)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Environment=RUST_LOG=info
EnvironmentFile=/etc/weltgewebe/projector.env
ExecStart=/usr/local/bin/weltgewebe-projector
Restart=on-failure
RestartSec=3

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
```

