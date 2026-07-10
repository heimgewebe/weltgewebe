<script lang="ts">
  import { authStore } from "$lib/auth/store";
  import type { Account } from "$lib/map/types";
  import {
    describeGarnrolleVisibility,
    findOwnGarnrolle,
  } from "$lib/garnrolle/visibility";

  export let accounts: Account[] = [];
  export let accountsLoadError: string | null = null;

  let draftKey = "";
  let displayName = "";
  let summary = "";
  let skills = "";
  let goods = "";
  let interests = "";
  let address = "";
  let visibilityChoice: "not_on_map" | "exact" | "radius" = "not_on_map";
  let radiusM = 250;

  $: ownGarnrolle = findOwnGarnrolle(accounts, $authStore.account_id);
  $: visibility = describeGarnrolleVisibility(ownGarnrolle);
  $: currentKey = `${$authStore.account_id ?? "guest"}:${ownGarnrolle?.id ?? "unlisted"}`;

  $: if (currentKey !== draftKey) {
    draftKey = currentKey;
    displayName = ownGarnrolle?.title ?? "Meine Garnrolle";
    summary = ownGarnrolle?.summary ?? "";
    skills =
      ownGarnrolle?.tags
        ?.filter((tag) => tag !== "account" && tag !== "garnrolle")
        .join(", ") ?? "";
    goods = "";
    interests = "";
    address = "";
    visibilityChoice = visibility.state;
    radiusM =
      ownGarnrolle?.radius_m && ownGarnrolle.radius_m > 0
        ? ownGarnrolle.radius_m
        : 250;
  }

  $: mapHref = ownGarnrolle?.public_pos
    ? `/map?focus=garnrolle:${ownGarnrolle.id}`
    : "/map";
</script>

<section
  id="meine-garnrolle"
  class="my-garnrolle"
  data-testid="my-garnrolle-section"
>
  <div class="section-head">
    <div>
      <p class="eyebrow">Meine Garnrolle</p>
      <h2>Deine Garnrolle ist dein Anfang im Gewebe.</h2>
    </div>
    <span class="state-pill" data-state={visibility.state}
      >{visibility.label}</span
    >
  </div>

  {#if !$authStore.authenticated}
    <div class="empty-card" data-testid="my-garnrolle-anonymous">
      <p>
        Du bist noch nicht angemeldet. Nach dem Login entsteht deine Garnrolle.
      </p>
      <a class="btn btn-primary" href="/login">Login starten</a>
    </div>
  {:else}
    <div class="status-card" data-testid="my-garnrolle-status">
      <div>
        <strong>{visibility.label}</strong>
        <p>{visibility.description}</p>
        {#if accountsLoadError}
          <p class="warn">
            Garnrollen-Daten konnten nicht geladen werden: {accountsLoadError}
          </p>
        {:else if !ownGarnrolle}
          <p class="muted">
            Deine Sitzung ist aktiv. Es gibt noch keinen öffentlichen
            Garnrollen-Datensatz für diesen Account. Produktsprachlich heißt
            das: Die Garnrolle ist angelegt, aber noch nicht auf der Karte.
          </p>
        {/if}
      </div>
      <a
        class="btn"
        href={mapHref}
        aria-disabled={!visibility.canZoomToMap}
        data-testid="my-garnrolle-map-link"
      >
        {visibility.canZoomToMap ? "Auf Karte zeigen" : "Karte öffnen"}
      </a>
    </div>

    <form class="garnrolle-form" aria-describedby="my-garnrolle-save-note">
      <fieldset>
        <legend>Garnrolle beschreiben</legend>
        <label>
          Anzeigename
          <input bind:value={displayName} placeholder="Meine Garnrolle" />
        </label>
        <label>
          Kurzbeschreibung
          <textarea
            bind:value={summary}
            rows="3"
            placeholder="Was bringst du ins Gewebe ein?"></textarea>
        </label>
        <label>
          Fähigkeiten
          <input
            bind:value={skills}
            placeholder="z. B. Holzbau, Organisation, Kochen"
          />
        </label>
        <label>
          Güter
          <input
            bind:value={goods}
            placeholder="z. B. Werkzeug, Raum, Lastenrad"
          />
        </label>
        <label>
          Interessen
          <input
            bind:value={interests}
            placeholder="z. B. Fairschenken, Nachbarschaft, Commons"
          />
        </label>
      </fieldset>

      <fieldset>
        <legend>Garnrolle auf Karte setzen</legend>
        <label>
          Adresse
          <input bind:value={address} placeholder="Poelsweg 2, Hamburg" />
        </label>

        <div class="radio-group" role="radiogroup" aria-label="Sichtbarkeit">
          <label class="radio-card">
            <input
              type="radio"
              bind:group={visibilityChoice}
              value="not_on_map"
            />
            <span>
              <strong>Noch nicht auf der Karte</strong>
              <small>Keine öffentliche Kartenposition.</small>
            </span>
          </label>
          <label class="radio-card">
            <input type="radio" bind:group={visibilityChoice} value="exact" />
            <span>
              <strong>Exakt sichtbar</strong>
              <small
                >Die angegebene Position wird sichtbar. Das ist ein regulärer
                positiver Fall.</small
              >
            </span>
          </label>
          <label class="radio-card">
            <input type="radio" bind:group={visibilityChoice} value="radius" />
            <span>
              <strong>Im Umkreis sichtbar</strong>
              <small>Die Garnrolle erscheint nur ungefähr.</small>
            </span>
          </label>
        </div>

        {#if visibilityChoice === "radius"}
          <label>
            Radius in Metern
            <input
              type="number"
              min="50"
              max="5000"
              step="50"
              bind:value={radiusM}
            />
          </label>
        {/if}
      </fieldset>

      <div class="actions">
        <button type="button" class="btn btn-primary" disabled>Speichern</button
        >
        <a class="btn" href="/map?compose=node">Ersten Knoten weben</a>
      </div>
      <p id="my-garnrolle-save-note" class="muted">
        Dieser Schnitt baut die Oberfläche und Semantik. Persistenz für Profil
        und Verortung folgt im nächsten API-Schnitt.
      </p>
    </form>
  {/if}
</section>

<style>
  .my-garnrolle {
    display: grid;
    gap: 1rem;
  }

  .section-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .section-head h2 {
    margin: 0.2rem 0 0;
  }

  .eyebrow {
    margin: 0;
    color: var(--muted, #9aa4b2);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .state-pill {
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.12));
    border-radius: 999px;
    color: var(--text, #e9eef5);
    font-size: 0.8rem;
    padding: 0.35rem 0.7rem;
    white-space: nowrap;
  }

  .state-pill[data-state="exact"] {
    background: rgba(84, 225, 166, 0.14);
  }

  .state-pill[data-state="radius"] {
    background: rgba(106, 166, 255, 0.16);
  }

  .state-pill[data-state="not_on_map"] {
    background: rgba(255, 255, 255, 0.05);
  }

  .status-card,
  .empty-card {
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
    border-radius: 12px;
    display: flex;
    gap: 1rem;
    justify-content: space-between;
    padding: 1rem;
  }

  .status-card p,
  .empty-card p {
    margin: 0.35rem 0 0;
  }

  .warn {
    color: #ffd28a;
  }

  .muted {
    color: var(--muted, #9aa4b2);
    font-size: 0.92rem;
  }

  .garnrolle-form {
    display: grid;
    gap: 1rem;
  }

  fieldset {
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
    border-radius: 12px;
    display: grid;
    gap: 0.9rem;
    margin: 0;
    padding: 1rem;
  }

  legend {
    font-weight: 700;
    padding: 0 0.35rem;
  }

  label {
    display: grid;
    gap: 0.35rem;
    font-weight: 600;
  }

  input,
  textarea {
    background: var(--bg, #0f1115);
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.12));
    border-radius: 8px;
    color: var(--text, #e9eef5);
    font: inherit;
    padding: 0.7rem;
  }

  .radio-group {
    display: grid;
    gap: 0.7rem;
  }

  .radio-card {
    align-items: flex-start;
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
    border-radius: 10px;
    display: grid;
    gap: 0.7rem;
    grid-template-columns: auto 1fr;
    padding: 0.75rem;
  }

  .radio-card small {
    color: var(--muted, #9aa4b2);
    display: block;
    font-weight: 400;
    margin-top: 0.25rem;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .btn {
    align-items: center;
    background: var(--panel-border, rgba(255, 255, 255, 0.08));
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.12));
    border-radius: 8px;
    color: var(--text, #e9eef5);
    cursor: pointer;
    display: inline-flex;
    font-weight: 700;
    justify-content: center;
    min-height: 42px;
    padding: 0 0.9rem;
    text-decoration: none;
  }

  .btn-primary {
    background: var(--accent, #6aa6ff);
    color: #0f1115;
  }

  .btn:disabled,
  .btn[aria-disabled="true"] {
    cursor: not-allowed;
    opacity: 0.55;
  }

  @media (max-width: 640px) {
    .section-head,
    .status-card,
    .empty-card {
      display: grid;
    }
  }
</style>
