<script>
  import '../app.css';
  import 'maplibre-gl/dist/maplibre-gl.css';

  export let data;
</script>

<svelte:head>
  {#if data?.canonical}
    <link rel="canonical" href={data.canonical} />
  {/if}
</svelte:head>

<slot />
