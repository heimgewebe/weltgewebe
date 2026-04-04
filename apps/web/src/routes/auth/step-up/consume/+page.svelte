<script lang="ts">
  import { page } from '$app/stores';

  $: token = $page.url.searchParams.get('token');
  $: challengeId = $page.url.searchParams.get('challenge_id');
  let status: 'idle' | 'loading' | 'success' | 'error' | 'invalid' = 'idle';

  $: {
    if (!token || !challengeId) {
      status = 'invalid';
    } else if (status === 'invalid') {
      status = 'idle';
    }
  }

  async function confirm() {
    if (!token || !challengeId) return;
    status = 'loading';
    try {
      const res = await fetch('/api/auth/step-up/magic-link/consume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, challenge_id: challengeId })
      });
      if (res.ok) {
        status = 'success';
      } else {
        status = 'error';
      }
    } catch (e) {
      status = 'error';
    }
  }
</script>

<div class="col" style="gap:1.5rem; padding:1.5rem; max-width:400px; margin:0 auto; margin-top: 10vh;">
  <div class="panel col" style="gap:1rem;">
    <h1>Aktion bestätigen</h1>
    {#if status === 'invalid'}
      <div style="color:var(--color-danger, #ff6b6b);">Dieser Bestätigungslink ist unvollständig oder ungültig. Bitte fordere einen neuen Link an.</div>
    {:else if status === 'success'}
      <div style="color:var(--color-theme-2, #2ecc71);">Die Aktion wurde erfolgreich bestätigt. Du kannst dieses Fenster nun schließen.</div>
    {:else if status === 'error'}
      <div style="color:var(--color-danger, #ff6b6b);">Ein Fehler ist aufgetreten oder der Link ist abgelaufen.</div>
    {:else}
      <p>Bitte klicke auf den Button, um die angeforderte Aktion freizugeben.</p>
      <button class="btn" disabled={status === 'loading'} on:click={confirm}>
        {status === 'loading' ? 'Wird bestätigt...' : 'Jetzt bestätigen'}
      </button>
    {/if}
  </div>
</div>
