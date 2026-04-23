<script lang="ts">
  const links = [
    {
      href: '/_dev/auth',
      title: 'Login / Auth',
      description: 'Entwickler-Login mit verschiedenen Rollen (Admin, Weber, Gast).'
    },
    {
      href: '/_dev/gestures',
      title: 'Swipe Playground',
      description:
        'Teste die Swipe-Action mit konfigurierbaren Schwellenwerten und sieh dir Events live an.'
    }
  ];
</script>

<svelte:head>
  <title>Dev-Werkzeuge</title>
</svelte:head>

<div class="col" style="gap:1.5rem; padding:1.5rem; max-width:720px; margin:0 auto;">
  <header class="col" style="gap:.25rem;">
    <h1>Dev-Werkzeuge</h1>
    <p class="ghost" style="margin:0;">
      Interne Helferlein für lokale Entwicklung. Diese Seiten sind nicht Teil des Produktiv-Builds.
    </p>
  </header>

  <ul class="col" style="gap:1rem; margin:0; padding:0; list-style:none;">
    {#each links as link}
      <li class="panel col" style="gap:.5rem;">
        <h2 style="margin:0; font-size:1.1rem;">{link.title}</h2>
        <p class="ghost" style="margin:0;">{link.description}</p>
        <div class="row" style="justify-content:flex-end;">
          <a class="btn" rel="nofollow" href={link.href}>Öffnen</a>
        </div>
      </li>
    {/each}
  </ul>
</div>
