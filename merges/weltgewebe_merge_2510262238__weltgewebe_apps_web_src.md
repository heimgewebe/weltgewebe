### 📄 weltgewebe/apps/web/src/app.css

**Größe:** 1 KB | **md5:** `4471946c3c1af41300f0c6804b38f808`

```css
/* Minimal, utility-light Styles für Click-Dummy */
:root { --bg:#0b0e12; --fg:#e7ebee; --muted:#9aa3ad; --panel:#141a21; --accent:#7cc4ff; }
html,body,#app { height:100%; margin:0; }
body { background:var(--bg); color:var(--fg); font: 14px/1.4 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial; }
.row { display:flex; gap:.75rem; align-items:center; }
.col { display:flex; flex-direction:column; gap:.5rem; }
.panel { background:var(--panel); border:1px solid #1f2630; border-radius:12px; padding:.75rem; }
.badge { border:1px solid #223244; padding:.15rem .45rem; border-radius:999px; color:var(--muted); }
.ghost { opacity:.7 }
.divider { height:1px; background:#1f2630; margin:.5rem 0; }
.btn { padding:.4rem .6rem; border:1px solid #263240; background:#101821; color:var(--fg); border-radius:8px; cursor:pointer }
.btn:disabled { opacity:.5; cursor:not-allowed }
.legend-dot { width:.8rem; height:.8rem; border-radius:999px; display:inline-block; margin-right:.4rem; vertical-align:middle }
.dot-blue{background:#4ea1ff}.dot-gray{background:#9aa3ad}.dot-yellow{background:#ffd65a}.dot-red{background:#ff6b6b}.dot-green{background:#54e1a6}.dot-violet{background:#b392f0}
```

### 📄 weltgewebe/apps/web/src/app.d.ts

**Größe:** 112 B | **md5:** `c20a78b8e768a570c00cb0fd7e016b4e`

```typescript
// See https://kit.svelte.dev/docs/types
// for information about these interfaces
declare global {}
export {};
```

### 📄 weltgewebe/apps/web/src/app.html

**Größe:** 286 B | **md5:** `e8f20d9bbdd6b5d1b19d651a703e0d1a`

```html
<!doctype html>
<html lang="en">
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		%sveltekit.head%
	</head>
	<body data-sveltekit-preload-data="hover">
		<div style="display: contents">%sveltekit.body%</div>
	</body>
</html>
```

