### 📄 apps/web/.gitignore

**Größe:** 154 B | **md5:** `54f7490e482e03a6a348adfd9aa787f6`

```plaintext
node_modules
.svelte-kit
build
.DS_Store
public/demo.png
.env
.env.local

# Playwright artifacts
playwright-report/
test-results/
blob-report/
trace.zip
```

### 📄 apps/web/.npmrc

**Größe:** 19 B | **md5:** `e780ac33d3d13827a73886735c3a368b`

```plaintext
engine-strict=true
```

### 📄 apps/web/README.md

**Größe:** 2 KB | **md5:** `3c3b18af589bba248f7f848f79e7776b`

```markdown
# weltgewebe-web (Gate A Click-Dummy)

Frontend-only Prototyp zur Diskussion von UX und Vokabular (Karte, Knoten, Fäden, Drawer, Zeitachse).

## Dev

```bash
cd apps/web
npm ci
npm run dev
```

Standardmäßig läuft der Dev-Server auf `http://localhost:5173/map`.
In Container- oder Codespaces-Umgebungen kannst du optional `npm run dev -- --host --port 5173`
verwenden.

> [!NOTE]
> **Node-Version:** Bitte Node.js ≥ 20.19 (oder ≥ 22.12) verwenden – darunter verweigern Vite und Freunde den Dienst.

### Polyfill-Debugging

Für ältere Safari-/iPadOS-Versionen wird automatisch ein `inert`-Polyfill aktiviert.
Falls du das native Verhalten prüfen möchtest, hänge `?noinert=1` an die URL
(oder setze `window.__NO_INERT__ = true` im DevTools-Console).

### Screenshot aufnehmen

In einem zweiten Terminal (während `npm run dev` läuft):

```bash
npm run screenshot
```

Legt `public/demo.png` an.

## Was kann das?

- Vollbild-Karte (MapLibre) mit 4 Strukturknoten (Platzhalter).
- Linker/rechter Drawer (UI-Stubs), Legende, Zeitachsen-Stub im Footer.
- Keine Persistenz, keine echten Filter/Abfragen (Ethik → UX → Gemeinschaft → Zukunft → Autonomie → Kosten).

## Nächste Schritte

- A-2: Klick auf Marker öffnet Panel mit „Was passiert hier später?“
- A-3: Dummy-Datenlayer (JSON) für 2–3 Knotentypen, 2 Fadenfarben
- A-4: Accessibility-Pass 1 (Fokus, Kontrast)
- A-5: Dev-Overlay: Bundle-Größe (Budget ≤ ~90KB Initial-JS)

## Tests

### Playwright (Drawer + Keyboard)

```bash
npx playwright install --with-deps  # einmalig
npx playwright test tests/drawers.spec.ts
```

Die Tests setzen in `beforeEach` das Flag `window.__E2E__ = true`, damit Maus-Drags die Swipe-Gesten simulieren können.
```

### 📄 apps/web/eslint.config.js

**Größe:** 964 B | **md5:** `07731461ec97002acab7a87a553106af`

```javascript
import js from "@eslint/js";
import globals from "globals";
import svelte from "eslint-plugin-svelte";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

const IGNORE = [
  ".svelte-kit/",
  "build/",
  "dist/",
  "node_modules/",
  "public/demo.png",
  "scripts/record-screenshot.mjs"
];

export default [
  {
    ignores: IGNORE
  },
  ...svelte.configs["flat/recommended"],
  {
    files: ["**/*.svelte"],
    rules: {
      "svelte/no-at-html-tags": "error"
    }
  },
  {
    files: ["**/*.ts", "**/*.js"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2023,
        sourceType: "module"
      },
      globals: globals.browser
    },
    plugins: {
      "@typescript-eslint": tsPlugin
    },
    rules: {
      ...js.configs.recommended.rules,
      ...tsPlugin.configs["recommended"].rules,
      "@typescript-eslint/no-explicit-any": "off"
    }
  }
];
```

### 📄 apps/web/package-lock.json

**Größe:** 63 KB | **md5:** `d306b5235616f5e9d79048e2ae6fbadc`

```json
{
  "name": "weltgewebe-web",
  "version": "0.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "weltgewebe-web",
      "version": "0.0.0",
      "hasInstallScript": true,
      "dependencies": {
        "maplibre-gl": "4.7.1"
      },
      "devDependencies": {
        "@playwright/test": "1.55.1",
        "@sveltejs/adapter-auto": "6.1.0",
        "@sveltejs/kit": "^2.47.2",
        "@typescript-eslint/eslint-plugin": "8.8.0",
        "@typescript-eslint/parser": "8.8.0",
        "eslint": "9.11.1",
        "eslint-plugin-svelte": "2.45.1",
        "globals": "15.9.0",
        "playwright": "1.55.1",
        "prettier": "3.3.3",
        "prettier-plugin-svelte": "3.2.6",
        "svelte": "5.39.6",
        "svelte-check": "^4.3.2",
        "typescript": "5.9.2",
        "vite": "^7.1.11"
      },
      "engines": {
        "node": ">=20.19.0"
      }
    },
    "node_modules/@esbuild/aix-ppc64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/aix-ppc64/-/aix-ppc64-0.25.10.tgz",
      "integrity": "sha512-0NFWnA+7l41irNuaSVlLfgNT12caWJVLzp5eAVhZ0z1qpxbockccEt3s+149rE64VUI3Ml2zt8Nv5JVc4QXTsw==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "aix"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm/-/android-arm-0.25.10.tgz",
      "integrity": "sha512-dQAxF1dW1C3zpeCDc5KqIYuZ1tgAdRXNoZP7vkBIRtKZPYe2xVr/d3SkirklCHudW1B45tGiUlz2pUWDfbDD4w==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm64/-/android-arm64-0.25.10.tgz",
      "integrity": "sha512-LSQa7eDahypv/VO6WKohZGPSJDq5OVOo3UoFR1E4t4Gj1W7zEQMUhI+lo81H+DtB+kP+tDgBp+M4oNCwp6kffg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-x64/-/android-x64-0.25.10.tgz",
      "integrity": "sha512-MiC9CWdPrfhibcXwr39p9ha1x0lZJ9KaVfvzA0Wxwz9ETX4v5CHfF09bx935nHlhi+MxhA63dKRRQLiVgSUtEg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-arm64/-/darwin-arm64-0.25.10.tgz",
      "integrity": "sha512-JC74bdXcQEpW9KkV326WpZZjLguSZ3DfS8wrrvPMHgQOIEIG/sPXEN/V8IssoJhbefLRcRqw6RQH2NnpdprtMA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-x64/-/darwin-x64-0.25.10.tgz",
      "integrity": "sha512-tguWg1olF6DGqzws97pKZ8G2L7Ig1vjDmGTwcTuYHbuU6TTjJe5FXbgs5C1BBzHbJ2bo1m3WkQDbWO2PvamRcg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-arm64/-/freebsd-arm64-0.25.10.tgz",
      "integrity": "sha512-3ZioSQSg1HT2N05YxeJWYR+Libe3bREVSdWhEEgExWaDtyFbbXWb49QgPvFH8u03vUPX10JhJPcz7s9t9+boWg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-x64/-/freebsd-x64-0.25.10.tgz",
      "integrity": "sha512-LLgJfHJk014Aa4anGDbh8bmI5Lk+QidDmGzuC2D+vP7mv/GeSN+H39zOf7pN5N8p059FcOfs2bVlrRr4SK9WxA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm/-/linux-arm-0.25.10.tgz",
      "integrity": "sha512-oR31GtBTFYCqEBALI9r6WxoU/ZofZl962pouZRTEYECvNF/dtXKku8YXcJkhgK/beU+zedXfIzHijSRapJY3vg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm64/-/linux-arm64-0.25.10.tgz",
      "integrity": "sha512-5luJWN6YKBsawd5f9i4+c+geYiVEw20FVW5x0v1kEMWNq8UctFjDiMATBxLvmmHA4bf7F6hTRaJgtghFr9iziQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ia32": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ia32/-/linux-ia32-0.25.10.tgz",
      "integrity": "sha512-NrSCx2Kim3EnnWgS4Txn0QGt0Xipoumb6z6sUtl5bOEZIVKhzfyp/Lyw4C1DIYvzeW/5mWYPBFJU3a/8Yr75DQ==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-loong64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-loong64/-/linux-loong64-0.25.10.tgz",
      "integrity": "sha512-xoSphrd4AZda8+rUDDfD9J6FUMjrkTz8itpTITM4/xgerAZZcFW7Dv+sun7333IfKxGG8gAq+3NbfEMJfiY+Eg==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-mips64el": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-mips64el/-/linux-mips64el-0.25.10.tgz",
      "integrity": "sha512-ab6eiuCwoMmYDyTnyptoKkVS3k8fy/1Uvq7Dj5czXI6DF2GqD2ToInBI0SHOp5/X1BdZ26RKc5+qjQNGRBelRA==",
      "cpu": [
        "mips64el"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ppc64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ppc64/-/linux-ppc64-0.25.10.tgz",
      "integrity": "sha512-NLinzzOgZQsGpsTkEbdJTCanwA5/wozN9dSgEl12haXJBzMTpssebuXR42bthOF3z7zXFWH1AmvWunUCkBE4EA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-riscv64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-riscv64/-/linux-riscv64-0.25.10.tgz",
      "integrity": "sha512-FE557XdZDrtX8NMIeA8LBJX3dC2M8VGXwfrQWU7LB5SLOajfJIxmSdyL/gU1m64Zs9CBKvm4UAuBp5aJ8OgnrA==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-s390x": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-s390x/-/linux-s390x-0.25.10.tgz",
      "integrity": "sha512-3BBSbgzuB9ajLoVZk0mGu+EHlBwkusRmeNYdqmznmMc9zGASFjSsxgkNsqmXugpPk00gJ0JNKh/97nxmjctdew==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.25.10.tgz",
      "integrity": "sha512-QSX81KhFoZGwenVyPoberggdW1nrQZSvfVDAIUXr3WqLRZGZqWk/P4T8p2SP+de2Sr5HPcvjhcJzEiulKgnxtA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-arm64/-/netbsd-arm64-0.25.10.tgz",
      "integrity": "sha512-AKQM3gfYfSW8XRk8DdMCzaLUFB15dTrZfnX8WXQoOUpUBQ+NaAFCP1kPS/ykbbGYz7rxn0WS48/81l9hFl3u4A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-x64/-/netbsd-x64-0.25.10.tgz",
      "integrity": "sha512-7RTytDPGU6fek/hWuN9qQpeGPBZFfB4zZgcz2VK2Z5VpdUxEI8JKYsg3JfO0n/Z1E/6l05n0unDCNc4HnhQGig==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-arm64/-/openbsd-arm64-0.25.10.tgz",
      "integrity": "sha512-5Se0VM9Wtq797YFn+dLimf2Zx6McttsH2olUBsDml+lm0GOCRVebRWUvDtkY4BWYv/3NgzS8b/UM3jQNh5hYyw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-x64/-/openbsd-x64-0.25.10.tgz",
      "integrity": "sha512-XkA4frq1TLj4bEMB+2HnI0+4RnjbuGZfet2gs/LNs5Hc7D89ZQBHQ0gL2ND6Lzu1+QVkjp3x1gIcPKzRNP8bXw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openharmony-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openharmony-arm64/-/openharmony-arm64-0.25.10.tgz",
      "integrity": "sha512-AVTSBhTX8Y/Fz6OmIVBip9tJzZEUcY8WLh7I59+upa5/GPhh2/aM6bvOMQySspnCCHvFi79kMtdJS1w0DXAeag==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openharmony"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/sunos-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/sunos-x64/-/sunos-x64-0.25.10.tgz",
      "integrity": "sha512-fswk3XT0Uf2pGJmOpDB7yknqhVkJQkAQOcW/ccVOtfx05LkbWOaRAtn5SaqXypeKQra1QaEa841PgrSL9ubSPQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "sunos"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-arm64/-/win32-arm64-0.25.10.tgz",
      "integrity": "sha512-ah+9b59KDTSfpaCg6VdJoOQvKjI33nTaQr4UluQwW7aEwZQsbMCfTmfEO4VyewOxx4RaDT/xCy9ra2GPWmO7Kw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-ia32": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-ia32/-/win32-ia32-0.25.10.tgz",
      "integrity": "sha512-QHPDbKkrGO8/cz9LKVnJU22HOi4pxZnZhhA2HYHez5Pz4JeffhDjf85E57Oyco163GnzNCVkZK0b/n4Y0UHcSw==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-x64/-/win32-x64-0.25.10.tgz",
      "integrity": "sha512-9KpxSVFCu0iK1owoez6aC/s/EdUQLDN3adTxGCqxMVhrPDj6bt5dbrHDXUuq+Bs2vATFBBrQS5vdQ/Ed2P+nbw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@jridgewell/gen-mapping": {
      "version": "0.3.13",
      "resolved": "https://registry.npmjs.org/@jridgewell/gen-mapping/-/gen-mapping-0.3.13.tgz",
      "integrity": "sha512-2kkt/7niJ6MgEPxF0bYdQ6etZaA+fQvDcLKckhy1yIQOzaoKjBBjSj63/aLVjYE3qhRt5dvM+uUyfCg6UKCBbA==",
      "dev": true,
      "dependencies": {
        "@jridgewell/sourcemap-codec": "1.5.5",
        "@jridgewell/trace-mapping": "0.3.31"
      }
    },
    "node_modules/@jridgewell/remapping": {
      "version": "2.3.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/remapping/-/remapping-2.3.5.tgz",
      "integrity": "sha512-LI9u/+laYG4Ds1TDKSJW2YPrIlcVYOwi2fUC6xB43lueCjgxV4lffOCZCtYFiH6TNOX+tQKXx97T4IKHbhyHEQ==",
      "dev": true,
      "dependencies": {
        "@jridgewell/gen-mapping": "0.3.13",
        "@jridgewell/trace-mapping": "0.3.31"
      }
    },
    "node_modules/@jridgewell/resolve-uri": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/@jridgewell/resolve-uri/-/resolve-uri-3.1.2.tgz",
      "integrity": "sha512-bRISgCIjP20/tbWSPWMEi54QVPRZExkuD9lJL+UIxUKtwVJA8wW1Trb1jMs1RFXo1CBTNZ/5hpC9QvmKWdopKw==",
      "dev": true,
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@jridgewell/sourcemap-codec": {
      "version": "1.5.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
      "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
      "dev": true
    },
    "node_modules/@jridgewell/trace-mapping": {
      "version": "0.3.31",
      "resolved": "https://registry.npmjs.org/@jridgewell/trace-mapping/-/trace-mapping-0.3.31.tgz",
      "integrity": "sha512-zzNR+SdQSDJzc8joaeP8QQoCQr8NuYx2dIIytl1QeBEZHJ9uW6hebsrYgbz8hJwUQao3TWCMtmfV8Nu1twOLAw==",
      "dev": true,
      "dependencies": {
        "@jridgewell/resolve-uri": "3.1.2",
        "@jridgewell/sourcemap-codec": "1.5.5"
      }
    },
    "node_modules/@mapbox/geojson-rewind": {
      "version": "0.5.2",
      "resolved": "https://registry.npmjs.org/@mapbox/geojson-rewind/-/geojson-rewind-0.5.2.tgz",
      "integrity": "sha512-tJaT+RbYGJYStt7wI3cq4Nl4SXxG8W7JDG5DMJu97V25RnbNg3QtQtf+KD+VLjNpWKYsRvXDNmNrBgEETr1ifA==",
      "dependencies": {
        "get-stream": "6.0.1",
        "minimist": "1.2.8"
      }
    },
    "node_modules/@mapbox/jsonlint-lines-primitives": {
      "version": "2.0.2",
      "resolved": "https://registry.npmjs.org/@mapbox/jsonlint-lines-primitives/-/jsonlint-lines-primitives-2.0.2.tgz",
      "integrity": "sha512-rY0o9A5ECsTQRVhv7tL/OyDpGAoUB4tTvLiW1DSzQGq4bvTPhNw1VpSNjDJc5GFZ2XuyOtSWSVN05qOtcD71qQ==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/@mapbox/point-geometry": {
      "version": "0.1.0",
      "resolved": "https://registry.npmjs.org/@mapbox/point-geometry/-/point-geometry-0.1.0.tgz",
      "integrity": "sha512-6j56HdLTwWGO0fJPlrZtdU/B13q8Uwmo18Ck2GnGgN9PCFyKTZ3UbXeEdRFh18i9XQ92eH2VdtpJHpBD3aripQ=="
    },
    "node_modules/@mapbox/tiny-sdf": {
      "version": "2.0.7",
      "resolved": "https://registry.npmjs.org/@mapbox/tiny-sdf/-/tiny-sdf-2.0.7.tgz",
      "integrity": "sha512-25gQLQMcpivjOSA40g3gO6qgiFPDpWRoMfd+G/GoppPIeP6JDaMMkMrEJnMZhKyyS6iKwVt5YKu02vCUyJM3Ug=="
    },
    "node_modules/@mapbox/unitbezier": {
      "version": "0.0.1",
      "resolved": "https://registry.npmjs.org/@mapbox/unitbezier/-/unitbezier-0.0.1.tgz",
      "integrity": "sha512-nMkuDXFv60aBr9soUG5q+GvZYL+2KZHVvsqFCzqnkGEf46U2fvmytHaEVc1/YZbiLn8X+eR3QzX1+dwDO1lxlw=="
    },
    "node_modules/@mapbox/vector-tile": {
      "version": "1.3.1",
      "resolved": "https://registry.npmjs.org/@mapbox/vector-tile/-/vector-tile-1.3.1.tgz",
      "integrity": "sha512-MCEddb8u44/xfQ3oD+Srl/tNcQoqTw3goGk2oLsrFxOTc3dUp+kAnby3PvAeeBYSMSjSPD1nd1AJA6W49WnoUw==",
      "dependencies": {
        "@mapbox/point-geometry": "0.1.0"
      }
    },
    "node_modules/@mapbox/whoots-js": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/@mapbox/whoots-js/-/whoots-js-3.1.0.tgz",
      "integrity": "sha512-Es6WcD0nO5l+2BOQS4uLfNPYQaNDfbot3X1XUoloz+x0mPDS3eeORZJl06HXjwBG1fOGwCRnzK88LMdxKRrd6Q==",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@maplibre/maplibre-gl-style-spec": {
      "version": "20.4.0",
      "resolved": "https://registry.npmjs.org/@maplibre/maplibre-gl-style-spec/-/maplibre-gl-style-spec-20.4.0.tgz",
      "integrity": "sha512-AzBy3095fTFPjDjmWpR2w6HVRAZJ6hQZUCwk5Plz6EyfnfuQW1odeW5i2Ai47Y6TBA2hQnC+azscjBSALpaWgw==",
      "dependencies": {
        "@mapbox/jsonlint-lines-primitives": "2.0.2",
        "@mapbox/unitbezier": "0.0.1",
        "json-stringify-pretty-compact": "4.0.0",
        "minimist": "1.2.8",
        "quickselect": "2.0.0",
        "rw": "1.3.3",
        "tinyqueue": "3.0.0"
      }
    },
    "node_modules/@playwright/test": {
      "version": "1.55.1",
      "resolved": "https://registry.npmjs.org/@playwright/test/-/test-1.55.1.tgz",
      "integrity": "sha512-IVAh/nOJaw6W9g+RJVlIQJ6gSiER+ae6mKQ5CX1bERzQgbC1VSeBlwdvczT7pxb0GWiyrxH4TGKbMfDb4Sq/ig==",
      "dev": true,
      "dependencies": {
        "playwright": "1.55.1"
      },
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@polka/url": {
      "version": "1.0.0-next.29",
      "resolved": "https://registry.npmjs.org/@polka/url/-/url-1.0.0-next.29.tgz",
      "integrity": "sha512-wwQAWhWSuHaag8c4q/KN/vCoeOJYshAIvMQwD4GpSb3OiZklFfvAgmj0VCBBImRpuF/aFgIRzllXlVX93Jevww==",
      "dev": true
    },
    "node_modules/@rollup/rollup-android-arm-eabi": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm-eabi/-/rollup-android-arm-eabi-4.52.3.tgz",
      "integrity": "sha512-h6cqHGZ6VdnwliFG1NXvMPTy/9PS3h8oLh7ImwR+kl+oYnQizgjxsONmmPSb2C66RksfkfIxEVtDSEcJiO0tqw==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-android-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm64/-/rollup-android-arm64-4.52.3.tgz",
      "integrity": "sha512-wd+u7SLT/u6knklV/ifG7gr5Qy4GUbH2hMWcDauPFJzmCZUAJ8L2bTkVXC2niOIxp8lk3iH/QX8kSrUxVZrOVw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-darwin-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-arm64/-/rollup-darwin-arm64-4.52.3.tgz",
      "integrity": "sha512-lj9ViATR1SsqycwFkJCtYfQTheBdvlWJqzqxwc9f2qrcVrQaF/gCuBRTiTolkRWS6KvNxSk4KHZWG7tDktLgjg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-darwin-x64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-x64/-/rollup-darwin-x64-4.52.3.tgz",
      "integrity": "sha512-+Dyo7O1KUmIsbzx1l+4V4tvEVnVQqMOIYtrxK7ncLSknl1xnMHLgn7gddJVrYPNZfEB8CIi3hK8gq8bDhb3h5A==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-arm64/-/rollup-freebsd-arm64-4.52.3.tgz",
      "integrity": "sha512-u9Xg2FavYbD30g3DSfNhxgNrxhi6xVG4Y6i9Ur1C7xUuGDW3banRbXj+qgnIrwRN4KeJ396jchwy9bCIzbyBEQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-x64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-x64/-/rollup-freebsd-x64-4.52.3.tgz",
      "integrity": "sha512-5M8kyi/OX96wtD5qJR89a/3x5x8x5inXBZO04JWhkQb2JWavOWfjgkdvUqibGJeNNaz1/Z1PPza5/tAPXICI6A==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-gnueabihf": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm-gnueabihf/-/rollup-linux-arm-gnueabihf-4.52.3.tgz",
      "integrity": "sha512-IoerZJ4l1wRMopEHRKOO16e04iXRDyZFZnNZKrWeNquh5d6bucjezgd+OxG03mOMTnS1x7hilzb3uURPkJ0OfA==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-musleabihf": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm-musleabihf/-/rollup-linux-arm-musleabihf-4.52.3.tgz",
      "integrity": "sha512-ZYdtqgHTDfvrJHSh3W22TvjWxwOgc3ThK/XjgcNGP2DIwFIPeAPNsQxrJO5XqleSlgDux2VAoWQ5iJrtaC1TbA==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-gnu": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-gnu/-/rollup-linux-arm64-gnu-4.52.3.tgz",
      "integrity": "sha512-NcViG7A0YtuFDA6xWSgmFb6iPFzHlf5vcqb2p0lGEbT+gjrEEz8nC/EeDHvx6mnGXnGCC1SeVV+8u+smj0CeGQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-musl": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-musl/-/rollup-linux-arm64-musl-4.52.3.tgz",
      "integrity": "sha512-d3pY7LWno6SYNXRm6Ebsq0DJGoiLXTb83AIPCXl9fmtIQs/rXoS8SJxxUNtFbJ5MiOvs+7y34np77+9l4nfFMw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-gnu": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-loong64-gnu/-/rollup-linux-loong64-gnu-4.52.3.tgz",
      "integrity": "sha512-3y5GA0JkBuirLqmjwAKwB0keDlI6JfGYduMlJD/Rl7fvb4Ni8iKdQs1eiunMZJhwDWdCvrcqXRY++VEBbvk6Eg==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-gnu": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-ppc64-gnu/-/rollup-linux-ppc64-gnu-4.52.3.tgz",
      "integrity": "sha512-AUUH65a0p3Q0Yfm5oD2KVgzTKgwPyp9DSXc3UA7DtxhEb/WSPfbG4wqXeSN62OG5gSo18em4xv6dbfcUGXcagw==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-gnu": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-riscv64-gnu/-/rollup-linux-riscv64-gnu-4.52.3.tgz",
      "integrity": "sha512-1makPhFFVBqZE+XFg3Dkq+IkQ7JvmUrwwqaYBL2CE+ZpxPaqkGaiWFEWVGyvTwZace6WLJHwjVh/+CXbKDGPmg==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-musl": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-riscv64-musl/-/rollup-linux-riscv64-musl-4.52.3.tgz",
      "integrity": "sha512-OOFJa28dxfl8kLOPMUOQBCO6z3X2SAfzIE276fwT52uXDWUS178KWq0pL7d6p1kz7pkzA0yQwtqL0dEPoVcRWg==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-s390x-gnu": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-s390x-gnu/-/rollup-linux-s390x-gnu-4.52.3.tgz",
      "integrity": "sha512-jMdsML2VI5l+V7cKfZx3ak+SLlJ8fKvLJ0Eoa4b9/vCUrzXKgoKxvHqvJ/mkWhFiyp88nCkM5S2v6nIwRtPcgg==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-gnu": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-x64-gnu/-/rollup-linux-x64-gnu-4.52.3.tgz",
      "integrity": "sha512-tPgGd6bY2M2LJTA1uGq8fkSPK8ZLYjDjY+ZLK9WHncCnfIz29LIXIqUgzCR0hIefzy6Hpbe8Th5WOSwTM8E7LA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-musl": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-x64-musl/-/rollup-linux-x64-musl-4.52.3.tgz",
      "integrity": "sha512-BCFkJjgk+WFzP+tcSMXq77ymAPIxsX9lFJWs+2JzuZTLtksJ2o5hvgTdIcZ5+oKzUDMwI0PfWzRBYAydAHF2Mw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-openharmony-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-openharmony-arm64/-/rollup-openharmony-arm64-4.52.3.tgz",
      "integrity": "sha512-KTD/EqjZF3yvRaWUJdD1cW+IQBk4fbQaHYJUmP8N4XoKFZilVL8cobFSTDnjTtxWJQ3JYaMgF4nObY/+nYkumA==",

<<TRUNCATED: max_file_lines=800>>
```

### 📄 apps/web/package.json

**Größe:** 2 KB | **md5:** `5c01fa550d6da7fdfc17efd620b1dc55`

```json
{
  "name": "weltgewebe-web",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "packageManager": "npm@10.9.0",
  "scripts": {
    "postinstall": "node ./scripts/verify-cookie-version.js",
    "dev": "svelte-kit dev --host",
    "prebuild": "svelte-kit sync",
    "build": "svelte-kit build",
    "preview": "svelte-kit preview --host",
    "check": "svelte-check --tsconfig ./tsconfig.json",
    "check:ci": "svelte-check --tsconfig ./tsconfig.json --fail-on-warnings",
    "format": "prettier -w .",
    "lint": "prettier -c . && eslint . --max-warnings=0",
    "screenshot": "node scripts/record-screenshot.mjs",
    "pretest": "npm run build",
    "test": "playwright test",
    "test:report": "playwright show-report",
    "test:ci": "playwright test --reporter=line",
    "test:setup": "node ./node_modules/@playwright/test/cli.js install --with-deps || true",
    "sync": "svelte-kit sync"
  },
  "overrides": {
    "cookie": "npm:cookie@0.7.2"
  },
  "devDependencies": {
    "@playwright/test": "1.55.1",
    "@sveltejs/adapter-auto": "6.1.0",
    "@sveltejs/kit": "^2.47.2",
    "@sveltejs/vite-plugin-svelte": "^5.0.0",
    "@typescript-eslint/eslint-plugin": "8.8.0",
    "@typescript-eslint/parser": "8.8.0",
    "eslint": "9.11.1",
    "eslint-plugin-svelte": "2.45.1",
    "globals": "15.9.0",
    "prettier": "3.3.3",
    "prettier-plugin-svelte": "3.2.6",
    "svelte": "5.39.6",
    "svelte-check": "^4.3.2",
    "typescript": "5.9.2",
    "vite": "^7.1.11"
  },
  "dependencies": {
    "maplibre-gl": "4.7.1"
  },
  "engines": {
    "node": ">=20.19.0"
  }
}
```

### 📄 apps/web/playwright.config.ts

**Größe:** 516 B | **md5:** `8defa238328f4df12a4aaeb2f08cb4b9`

```typescript
import { defineConfig } from "@playwright/test";

const PORT = Number(process.env.PORT ?? 4173);

export default defineConfig({
  testDir: "tests",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? undefined : 2,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry"
  },
  webServer: {
    command: `npm run preview -- --host 0.0.0.0 --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI
  }
});
```

### 📄 apps/web/svelte.config.js

**Größe:** 828 B | **md5:** `5d1516e9e5c7edceaf4d157c8e3b3f10`

```javascript
import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Siehe https://svelte.dev/docs/kit/integrations für Preprocessor-Infos
  preprocess: vitePreprocess(),

  kit: {
    // adapter-auto ist eine Factory – hier **aufrufen**:
    adapter: adapter(),
    /**
     * Align Vite runtime resolution with tsconfig.json "paths".
     * Matches:
     *   "$lib/*"        -> "src/lib/*"
     *   "$components/*" -> "src/lib/components/*"
     *   "$stores/*"     -> "src/lib/stores/*"
     *   "$routes/*"     -> "src/routes/*"
     */
    alias: {
      $lib: 'src/lib',
      $components: 'src/lib/components',
      $stores: 'src/lib/stores',
      $routes: 'src/routes'
    }
  }
};

export default config;
```

### 📄 apps/web/tsconfig.json

**Größe:** 281 B | **md5:** `94f57085f1b51f7a00f1d256d296f070`

```json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "types": ["svelte"],
    "strict": true,
    "baseUrl": ".",
    "paths": {
      "$lib/*": ["src/lib/*"],
      "$components/*": ["src/lib/components/*"],
      "$stores/*": ["src/lib/stores/*"]
    }
  }
}
```

### 📄 apps/web/vite.config.ts

**Größe:** 144 B | **md5:** `36ee2922d761662f3727c204f73380b2`

```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
export default defineConfig({
  plugins: [sveltekit()]
});
```

