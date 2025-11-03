### 📄 weltgewebe/infra/compose/sql/init/00_extensions.sql

**Größe:** 140 B | **md5:** `2dcecbff232b900dacd96d7bb6fdb12d`

```sql
-- optional: hilfreiche Extensions als Ausgangspunkt
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

