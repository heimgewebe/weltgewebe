<script lang="ts">
  export let title = "Weltgewebe – Click-Dummy";
  export let timeCursor: string = "T-0";
</script>

<div class="app-shell">
  <header class="app-bar panel" aria-label="Navigation und Status">
    <div class="brand">
      <div class="brand-main">
        <strong>{title}</strong>
        <span class="badge">Gate A</span>
      </div>
      <p class="brand-sub ghost">Frontend-only Prototype · UX vor Code</p>
    </div>
    <div class="header-actions">
      <slot name="gewebekonto" />
      <slot name="topright" />
    </div>
  </header>
  <main class="app-main">
    <slot />
  </main>
  <footer class="app-footer panel" aria-label="Zeitachse (Attrappe)">
    <div>Zeitachse: Cursor <span class="badge">{timeCursor}</span></div>
    <div class="ghost">Replay deaktiviert · Gate B/C folgen</div>
  </footer>
</div>

<style>
  .app-shell {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 0.75rem;
    padding: 0.75rem;
    box-sizing: border-box;
  }

  .app-bar {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .brand {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .brand-main {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .brand-sub {
    margin: 0;
  }

  .header-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .header-actions :global(.btn:focus-visible),
  .header-actions :global(button:focus-visible),
  .header-actions :global(a:focus-visible) {
    outline: 2px solid rgba(112, 184, 255, 0.9);
    outline-offset: 2px;
    border-radius: 0.5rem;
  }

  .app-main {
    position: relative;
    overflow: hidden;
    border-radius: 18px;
  }

  .app-footer {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  @media (min-width: 42rem) {
    .app-bar {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
    }

    .header-actions {
      flex-direction: row;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .app-footer {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
    }
  }
</style>
