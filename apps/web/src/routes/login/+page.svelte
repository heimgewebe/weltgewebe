<script lang="ts">
  import { authStore } from "$lib/auth/store";
  import "$lib/styles/page-system.css";

  let email = $state("");
  let error: string | null = $state(null);
  let success = $state(false);
  let loading = $state(false);

  async function handleSubmit() {
    loading = true;
    error = null;
    success = false;
    try {
      await authStore.requestLogin(email);
      success = true;
    } catch (e) {
      if (e instanceof Error && e.message.includes("disabled")) {
        error = "Öffentlicher Login ist derzeit deaktiviert.";
      } else {
        error = "Login fehlgeschlagen. Bitte versuche es erneut.";
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

<main class="wg-page" data-testid="login-page">
  <div class="wg-page__shell wg-page__shell--narrow">
    <section
      class="wg-card wg-card--padded wg-stack"
      aria-labelledby="login-heading"
    >
      <header class="wg-stack">
        <p class="wg-eyebrow">Gewebekonto</p>
        <h1 id="login-heading" class="wg-title wg-title--compact">Login</h1>
      </header>

      {#if success}
        <div class="wg-state wg-state--success" role="status">
          <p><strong>Postfach prüfen!</strong></p>
          <p>
            Falls deine E-Mail registriert ist, haben wir dir einen Login-Link
            gesendet.
          </p>
        </div>
      {:else}
        <form
          onsubmit={(event) => {
            event.preventDefault();
            void handleSubmit();
          }}
          class="wg-stack"
        >
          <div class="wg-field">
            <label class="wg-label" for="email">E-Mail</label>
            <input
              class="wg-control"
              id="email"
              type="email"
              bind:value={email}
              placeholder="du@example.com"
              autocomplete="email"
              required
              disabled={loading}
              aria-describedby={error ? "login-error" : undefined}
            />
          </div>

          {#if error}
            <div id="login-error" class="wg-state wg-state--error" role="alert">
              {error}
            </div>
          {/if}

          <div class="wg-actions">
            <button
              type="submit"
              class="wg-button wg-button--primary"
              disabled={loading || !email}
            >
              {#if loading}Wird gesendet…{:else}Login-Link senden{/if}
            </button>
          </div>
        </form>
      {/if}
    </section>
  </div>
</main>
