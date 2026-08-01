<script lang="ts">
  import AccountSection from "$lib/components/AccountSection.svelte";
  import MyGarnrolleSection from "$lib/components/MyGarnrolleSection.svelte";
  import type { PageData } from "./$types";

  export let data: PageData;
</script>

<div class="container">
  <h1>Einstellungen</h1>
  <p class="intro">
    Passe die Darstellung an. Deine Garnrolle besteht bereits. Hier beschreibst
    du sie, setzt freiwillig einen privaten Kartenanker und bestimmst ihre
    öffentliche Sichtbarkeit.
  </p>

  <div class="card">
    <h2>Darstellung</h2>
    <p class="ghost">
      „System“ folgt deinem Gerät. Die Auswahl bleibt nur in diesem Browser.
    </p>
    <label class="row">
      <span>Farbschema</span>
      <select class="btn" data-wg-theme-control data-testid="theme-select">
        <option value="system">System</option>
        <option value="light">Hell</option>
        <option value="dark">Dunkel</option>
      </select>
    </label>
  </div>

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

  h2 {
    margin-top: 0;
  }

  .intro {
    margin-bottom: 2rem;
    color: var(--muted);
  }

  .card {
    background: var(--weave), var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: var(--radius);
    margin-bottom: 24px;
    padding: 24px;
    box-shadow: var(--shadow);
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
