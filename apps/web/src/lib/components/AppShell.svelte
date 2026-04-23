<div class="app-shell">
  <main class="app-main">
    <slot />
  </main>
</div>

<style>
  .app-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  .app-main {
    flex: 1;
    position: relative;
    overflow: hidden;
  }
</style>
