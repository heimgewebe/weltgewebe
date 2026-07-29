<script lang="ts">
  import AccountSection from "$lib/components/AccountSection.svelte";
  import MyGarnrolleSection from "$lib/components/MyGarnrolleSection.svelte";
  import type { PageData } from "./$types";

  export let data: PageData;
</script>

<div class="container">
  <h1>Einstellungen</h1>
  <p class="intro">
    Deine Garnrolle besteht bereits. Hier beschreibst du sie, setzt freiwillig
    einen privaten Kartenanker und bestimmst ihre öffentliche Sichtbarkeit.
  </p>

  <div class="card primary-card">
    <MyGarnrolleSection
      accounts={data.accounts}
      accountsLoadError={data.accountsLoadError}
    />
  </div>

  <div class="card">
    <AccountSection />
  </div>

  <p class="diagnostics-link">
    <a href="/build" data-testid="build-diagnostics-link">
      Technische Build-Diagnose
    </a>
  </p>
</div>

<style>
  .container {
    color: var(--text);
    margin: 40px auto;
    max-width: 760px;
    padding: 0 20px;
  }

  h1 {
    font-size: 2rem;
    margin-bottom: 1rem;
  }

  .intro {
    margin-bottom: 2rem;
    opacity: 0.8;
  }

  .card {
    background: var(--panel, #141a21);
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.06));
    border-radius: 12px;
    margin-bottom: 24px;
    padding: 24px;
  }

  .primary-card {
    padding: 0;
  }

  .primary-card :global(.my-garnrolle) {
    padding: 24px;
  }

  .diagnostics-link {
    margin: 0;
  }
</style>
