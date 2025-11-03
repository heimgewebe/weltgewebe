### 📄 apps/web/src/lib/styles/tokens.css

**Größe:** 923 B | **md5:** `3ffc03d6624bf43f77d5b0aa1a7603e8`

```css
:root{
  --bg: #0f1115;
  --panel: rgba(20,22,28,0.92);
  --panel-border: rgba(255,255,255,0.06);
  --text: #e9eef5;
  --muted: #9aa4b2;
  --accent: #6aa6ff;
  --accent-soft: rgba(106,166,255,0.18);
  --radius: 12px;
  --shadow: 0 6px 24px rgba(0,0,0,0.35);
  /* Layout- und Drawer-Defaults */
  --toolbar-offset: 52px;
  --drawer-gap: 12px;
  --drawer-width: 360px;
  --drawer-slide-offset: 20px;

  /* Swipe-Edge Defaults (innenliegende Greifzonen, kollisionsarm mit OS-Gesten) */
  --edge-inset-x: 24px;     /* Abstand von links/rechts */
  --edge-inset-top: 24px;   /* Abstand oben */
  --edge-top-height: 16px;  /* Höhe Top-Zone */
  --edge-left-width: 16px;  /* Breite linke Zone */
  --edge-right-width: 16px; /* Breite rechte Zone */
}

/* Android: Back-Swipe oft breiter → Zone schmaler & leicht weiter innen */
:root.ua-android{
  --edge-inset-x: 28px;
  --edge-left-width: 12px;
  --edge-right-width: 12px;
}
```

