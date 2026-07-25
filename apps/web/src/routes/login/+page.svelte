<script lang="ts">
  import "$lib/styles/page-foundation.css";
  import { authStore } from "$lib/auth/store";

  let email = "";
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
    } catch (cause) {
      if (cause instanceof Error && cause.message.includes("disabled")) {
        error = "Öffentlicher Login ist derzeit deaktiviert.";
      } else {
        error = "Anmeldung fehlgeschlagen. Bitte versuche es erneut.";
      }
      console.error(cause);
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Anmelden · Weltgewebe</title>
  <meta
    name="description"
    content="Im Weltgewebe anmelden, um Commons gemeinsam zu pflegen und zu verändern."
  />
</svelte:head>

<main class="wg-page wg-page--center" aria-labelledby="login-heading">
  <div class="wg-page__inner wg-page__inner--narrow">
    <a class="wg-back-link" href="/map">← Zum Gewebe</a>

    <header class="wg-page__header">
      <p class="wg-eyebrow">Gemeingüter gemeinsam verwalten</p>
      <h1 id="login-heading" class="wg-title wg-title--compact">Anmelden</h1>
      <p class="wg-lede">
        Mit deiner E-Mail erhältst du einen einmaligen Anmeldelink. Ein Passwort
        ist nicht nötig.
      </p>
    </header>

    <section class="wg-surface wg-surface--padded wg-surface--accent">
      {#if success}
        <div class="wg-status wg-status--success wg-stack" role="status">
          <strong>Postfach prüfen</strong>
          <p>
            Falls deine E-Mail registriert ist, haben wir dir einen Anmeldelink
            gesendet.
          </p>
        </div>
      {:else}
        <form on:submit|preventDefault={handleSubmit} class="wg-stack">
          <div class="wg-field">
            <label for="email">E-Mail-Adresse</label>
            <input
              class="wg-input"
              id="email"
              type="email"
              bind:value={email}
              placeholder="du@example.com"
              autocomplete="email"
              inputmode="email"
              aria-describedby="email-hint"
              required
              disabled={loading}
            />
            <span id="email-hint" class="wg-muted">
              Der Link kann nur einmal verwendet werden und läuft automatisch
              ab.
            </span>
          </div>

          {#if error}
            <div class="wg-status wg-status--error" role="alert">{error}</div>
          {/if}

          <div class="login-actions">
            <button
              type="submit"
              class="wg-button wg-button--primary"
              disabled={loading || !email}
            >
              {loading ? "Wird gesendet…" : "Anmeldelink senden"}
            </button>
          </div>
        </form>
      {/if}
    </section>
  </div>
</main>

<style>
  .login-actions {
    display: flex;
    justify-content: flex-end;
  }

  @media (max-width: 480px) {
    .login-actions .wg-button {
      width: 100%;
    }
  }
</style>
