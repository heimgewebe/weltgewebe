<script lang="ts">
  import { authStore } from '$lib/auth/store';

  let email = '';
  let error: string | null = null;
  let success = false;
  let loading = false;

  async function handleSubmit() {
    loading = true;
    error = null;
    success = false;
    try {
      await authStore.requestLogin(email);
      success = true;
    } catch (e) {
      if (e instanceof Error && e.message.includes('disabled')) {
        error = 'Öffentlicher Login ist derzeit deaktiviert.';
      } else {
        error = 'Login fehlgeschlagen. Bitte versuche es erneut.';
      }
      console.error(e);
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Login</title>
</svelte:head>

<div class="col" style="gap:1.5rem; padding:1.5rem; max-width:400px; margin:0 auto; margin-top: 10vh;">
  <div class="panel col" style="gap:1rem;">
    <h1 style="margin:0; font-size:1.5rem;">Login</h1>

    {#if success}
      <div class="panel" style="border-color:var(--color-theme-2, #2ecc71);">
        <p><strong>Postfach prüfen!</strong></p>
        <p>Falls deine E-Mail registriert ist, haben wir dir einen Login-Link gesendet.</p>
      </div>
    {:else}
      <form on:submit|preventDefault={handleSubmit} class="col" style="gap:1rem;">
        <div class="col">
          <label for="email" style="font-size:0.9rem; color:var(--muted);">E-Mail</label>
          <input
            id="email"
            type="email"
            bind:value={email}
            placeholder="du@beispiel.de"
            required
            disabled={loading}
            style="padding:0.5rem; border-radius:6px; border:1px solid #263240; background:#101821; color:white;"
          />
        </div>

        {#if error}
          <div style="color:var(--color-danger, #ff6b6b); font-size:0.9rem;">
            {error}
          </div>
        {/if}

        <div class="row" style="justify-content:flex-end;">
          <button type="submit" class="btn" disabled={loading || !email}>
            {#if loading}Wird gesendet...{:else}Login-Link senden{/if}
          </button>
        </div>
      </form>
    {/if}
  </div>
</div>
