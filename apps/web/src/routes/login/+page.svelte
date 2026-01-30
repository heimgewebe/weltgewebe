<script lang="ts">
  import { authStore } from '$lib/auth/store';
  import { goto } from '$app/navigation';

  let accountId = '';
  let error: string | null = null;
  let loading = false;

  async function handleSubmit() {
    loading = true;
    error = null;
    try {
      await authStore.login(accountId);
      await goto('/');
    } catch (e) {
      error = 'Login failed. Please check your Account ID.';
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

    <form on:submit|preventDefault={handleSubmit} class="col" style="gap:1rem;">
      <div class="col">
        <label for="account_id" style="font-size:0.9rem; color:var(--muted);">Account ID</label>
        <input
          id="account_id"
          type="text"
          bind:value={accountId}
          placeholder="z.B. user-123"
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
        <button type="submit" class="btn" disabled={loading || !accountId}>
          {#if loading}Logging in...{:else}Login{/if}
        </button>
      </div>
    </form>
  </div>
</div>
