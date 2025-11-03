### 📄 contracts/semantics/.upstream

**Größe:** 54 B | **md5:** `5b69f8d0a21f4d7ad4719b99f0873d62`

```plaintext
repo: semantAH
path: contracts/semantics
mode: mirror
```

### 📄 contracts/semantics/README.md

**Größe:** 111 B | **md5:** `01d4ab919007afe03e6aa996c9b3b3ae`

```markdown
# Semantik-Verträge (Upstream: semantAH)

Quelle: externer Ableger `semantAH`. Nicht editieren, nur spiegeln.
```

### 📄 contracts/semantics/edge.schema.json

**Größe:** 302 B | **md5:** `8f92b25fdd52e7dc7a589f36c9ed0a3a`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemEdge","type":"object",
  "required":["src","dst","rel"],
  "properties":{"src":{"type":"string"},"dst":{"type":"string"},"rel":{"type":"string"},
    "weight":{"type":"number"},"why":{"type":"string"},"updated_at":{"type":"string"}}
}
```

### 📄 contracts/semantics/node.schema.json

**Größe:** 358 B | **md5:** `8a55023fb9d91f644833dbcd7243011b`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemNode","type":"object",
  "required":["id","type","title"],
  "properties":{"id":{"type":"string"},"type":{"type":"string"},
    "title":{"type":"string"},"tags":{"type":"array","items":{"type":"string"}},
    "source":{"type":"string"},"updated_at":{"type":"string","format":"date-time"}}
}
```

### 📄 contracts/semantics/report.schema.json

**Größe:** 311 B | **md5:** `66113d119045d16fdbfdba885d82fb73`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemReport","type":"object",
  "required":["kind","created_at"],
  "properties":{"kind":{"type":"string"},"created_at":{"type":"string","format":"date-time"},
    "notes":{"type":"array","items":{"type":"string"}},
    "stats":{"type":"object"}}
}
```

