### 📄 apps/web/src/routes/archive/+page.svelte

**Größe:** 2 KB | **md5:** `a5c4de02e1586fe81976f4aabc4bbbcf`

```svelte
<script lang="ts">
  const archiveMonths = [
    { label: "Mai 2024", path: "/archive/2024/05" },
    { label: "April 2024", path: "/archive/2024/04" },
    { label: "März 2024", path: "/archive/2024/03" }
  ];
</script>

<svelte:head>
  <title>Archiv · Webrat</title>
  <meta
    name="description"
    content="Monatsarchiv der Webrat-Einträge mit einer Übersicht vergangener Beiträge."
  />
</svelte:head>

<main class="archive">
  <header>
    <h1>Archiv</h1>
    <p>
      Im Archiv findest du vergangene Monatsübersichten. Wähle einen Monat aus, um alle Einträge
      aus dieser Zeitspanne zu entdecken.
    </p>
  </header>

  <section aria-labelledby="archive-months">
    <h2 id="archive-months">Monate</h2>
    <ul>
      {#each archiveMonths as month}
        <li><a href={month.path}>{month.label}</a></li>
      {/each}
    </ul>
  </section>
</main>

<style>
  main.archive {
    max-width: 48rem;
    margin: 0 auto;
    padding: 2rem 1.5rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  header p {
    margin-top: 0.75rem;
    line-height: 1.6;
  }

  section ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.75rem;
  }

  section li {
    background: #f7f7f7;
    border-radius: 0.5rem;
    padding: 0.85rem 1rem;
    transition: background 0.2s ease-in-out, transform 0.2s ease-in-out;
  }

  section li:hover,
  section li:focus-within {
    background: #ececec;
    transform: translateY(-1px);
  }

  section a {
    color: inherit;
    text-decoration: none;
    font-weight: 600;
  }
</style>
```

