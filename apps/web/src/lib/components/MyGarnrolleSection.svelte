<script lang="ts">
  import { browser } from "$app/environment";
  import { goto, invalidateAll } from "$app/navigation";
  import { authStore } from "$lib/auth/store";
  import {
    ApiRequestError,
    getOwnGarnrolleProfile,
    updateOwnGarnrolle,
    type OwnGarnrolleProfile,
  } from "$lib/api/domainWrites";
  import type { Account, GarnrolleMapState, Location } from "$lib/map/types";
  import {
    describeGarnrolleVisibility,
    findOwnGarnrolle,
  } from "$lib/garnrolle/visibility";
  import { tick } from "svelte";

  export let accounts: Account[] = [];
  export let accountsLoadError: string | null = null;

  type GarnrolleDraft = {
    displayName: string;
    summary: string;
    skills: string;
    goods: string;
    interests: string;
    address: string;
    visibilityChoice: GarnrolleMapState;
    radiusM: number;
    selectedLocation: Location | null;
  };

  let profileKey = "";
  let displayName = "";
  let summary = "";
  let skills = "";
  let goods = "";
  let interests = "";
  let address = "";
  let visibilityChoice: GarnrolleMapState = "not_on_map";
  let radiusM = 250;
  let selectedLocation: Location | null = null;
  let isLoadingProfile = false;
  let isSaving = false;
  let profileError: string | null = null;
  let draftMessage: string | null = null;
  let saveMessage: string | null = null;
  let locationButton: HTMLButtonElement | null = null;

  $: ownGarnrolle = findOwnGarnrolle(accounts, $authStore.account_id);
  $: visibility = describeGarnrolleVisibility(ownGarnrolle);
  $: activeAccountId =
    $authStore.authenticated && $authStore.account_id
      ? $authStore.account_id
      : null;
  $: canEdit = $authStore.authenticated;
  $: radiusIsValid =
    Number.isInteger(radiusM) && radiusM >= 50 && radiusM <= 5000;
  $: canSave =
    canEdit &&
    !!ownGarnrolle &&
    !!displayName.trim() &&
    !isLoadingProfile &&
    !isSaving &&
    (visibilityChoice === "not_on_map" || selectedLocation !== null) &&
    (visibilityChoice !== "radius" || radiusIsValid);
  $: mapHref = ownGarnrolle?.public_pos
    ? `/map?focus=garnrolle:${ownGarnrolle.id}`
    : "/map";

  $: if (activeAccountId && activeAccountId !== profileKey) {
    profileKey = activeAccountId;
    void loadPrivateProfile(activeAccountId);
  }
  $: if (!activeAccountId && profileKey) {
    profileKey = "";
    resetDraft();
  }

  function splitList(value: string): string[] {
    return value
      .split(",")
      .map((entry) => entry.trim())
      .filter((entry, index, all) => entry && all.indexOf(entry) === index);
  }

  function categoryValues(tags: string[], prefix: string): string[] {
    return tags
      .filter((tag) => tag.startsWith(prefix))
      .map((tag) => tag.slice(prefix.length))
      .filter(Boolean);
  }

  function profileSkills(tags: string[]): string[] {
    const prefixed = categoryValues(tags, "skill:");
    const legacy = tags.filter(
      (tag) =>
        tag !== "account" &&
        tag !== "garnrolle" &&
        !tag.startsWith("skill:") &&
        !tag.startsWith("good:") &&
        !tag.startsWith("interest:"),
    );
    return [...prefixed, ...legacy].filter(
      (entry, index, all) => all.indexOf(entry) === index,
    );
  }

  function draftStorageKey(accountId: string): string {
    return `weltgewebe:garnrolle-draft:${accountId}`;
  }

  function currentDraft(): GarnrolleDraft {
    return {
      displayName,
      summary,
      skills,
      goods,
      interests,
      address,
      visibilityChoice,
      radiusM,
      selectedLocation,
    };
  }

  function applyDraft(draft: Partial<GarnrolleDraft>) {
    if (typeof draft.displayName === "string") displayName = draft.displayName;
    if (typeof draft.summary === "string") summary = draft.summary;
    if (typeof draft.skills === "string") skills = draft.skills;
    if (typeof draft.goods === "string") goods = draft.goods;
    if (typeof draft.interests === "string") interests = draft.interests;
    if (typeof draft.address === "string") address = draft.address;
    if (
      draft.visibilityChoice === "not_on_map" ||
      draft.visibilityChoice === "exact" ||
      draft.visibilityChoice === "radius"
    ) {
      visibilityChoice = draft.visibilityChoice;
    }
    if (typeof draft.radiusM === "number" && Number.isFinite(draft.radiusM)) {
      radiusM = draft.radiusM;
    }
    if (
      draft.selectedLocation === null ||
      (typeof draft.selectedLocation?.lat === "number" &&
        typeof draft.selectedLocation?.lon === "number")
    ) {
      selectedLocation = draft.selectedLocation ?? null;
    }
  }

  function resetDraft() {
    displayName = "";
    summary = "";
    skills = "";
    goods = "";
    interests = "";
    address = "";
    visibilityChoice = "not_on_map";
    radiusM = 250;
    selectedLocation = null;
    profileError = null;
    draftMessage = null;
    saveMessage = null;
  }

  function applyProfile(profile: OwnGarnrolleProfile) {
    displayName = profile.title;
    summary = profile.summary ?? "";
    skills = profileSkills(profile.tags).join(", ");
    goods = categoryValues(profile.tags, "good:").join(", ");
    interests = categoryValues(profile.tags, "interest:").join(", ");
    address = profile.address ?? "";
    visibilityChoice = profile.map_state;
    radiusM = profile.radius_m > 0 ? profile.radius_m : 250;
    selectedLocation = profile.location ?? null;
  }

  function returnedMapLocation(accountId: string): Location | null {
    if (!browser) return null;
    const key = `weltgewebe:garnrolle-return-location:${accountId}`;
    const stored = sessionStorage.getItem(key);
    sessionStorage.removeItem(key);
    if (!stored) return null;
    try {
      const value = JSON.parse(stored) as Partial<Location>;
      const lat = value.lat;
      const lon = value.lon;
      if (
        typeof lat !== "number" ||
        typeof lon !== "number" ||
        !Number.isFinite(lat) ||
        !Number.isFinite(lon) ||
        lat < -90 ||
        lat > 90 ||
        lon < -180 ||
        lon > 180
      ) {
        return null;
      }
      return { lat, lon };
    } catch {
      return null;
    }
  }

  async function loadPrivateProfile(accountId: string) {
    let focusReturnedLocation = false;
    isLoadingProfile = true;
    profileError = null;
    draftMessage = null;
    saveMessage = null;
    try {
      const profile = await getOwnGarnrolleProfile();
      if (profile.id !== accountId) {
        throw new Error("profile-account-mismatch");
      }
      applyProfile(profile);

      if (browser) {
        const stored = sessionStorage.getItem(draftStorageKey(accountId));
        if (stored) {
          try {
            applyDraft(JSON.parse(stored) as Partial<GarnrolleDraft>);
          } catch {
            sessionStorage.removeItem(draftStorageKey(accountId));
          }
        }
      }
      const returned = returnedMapLocation(accountId);
      if (returned) {
        selectedLocation = returned;
        draftMessage =
          "Privater Kartenanker übernommen, aber noch nicht gespeichert. Wähle nun die öffentliche Sichtbarkeit und speichere deine Garnrolle.";
        focusReturnedLocation = true;
      }
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 401) {
        profileError =
          "Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.";
      } else {
        profileError =
          "Deine Garnrolle konnte nicht vollständig geladen werden. Bitte lade die Seite neu.";
      }
    } finally {
      isLoadingProfile = false;
      if (focusReturnedLocation) {
        await tick();
        locationButton?.focus();
      }
    }
  }

  function saveDraftForMap() {
    if (!browser || !activeAccountId) return;
    sessionStorage.setItem(
      draftStorageKey(activeAccountId),
      JSON.stringify(currentDraft()),
    );
  }

  async function chooseMapLocation() {
    draftMessage = null;
    saveMessage = null;
    profileError = null;
    saveDraftForMap();
    await goto("/map?compose=garnrolle");
  }

  function profileTags(): string[] {
    return [
      ...splitList(skills).map((tag) => `skill:${tag}`),
      ...splitList(goods).map((tag) => `good:${tag}`),
      ...splitList(interests).map((tag) => `interest:${tag}`),
    ];
  }

  function describeSaveError(error: unknown): string {
    if (error instanceof ApiRequestError) {
      if (error.status === 401) {
        return "Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.";
      }
      if (error.status === 403) {
        return "Dein Konto darf die Garnrolle derzeit nicht bearbeiten.";
      }
      if (error.status === 400) {
        return "Bitte prüfe Anzeigename, Kartenanker und Sichtbarkeit.";
      }
    }
    return "Die Garnrolle konnte nicht gespeichert werden. Bitte versuche es erneut.";
  }

  async function handleSave(event: SubmitEvent) {
    event.preventDefault();
    profileError = null;
    draftMessage = null;
    saveMessage = null;
    if (!canSave || !activeAccountId) return;

    isSaving = true;
    try {
      await updateOwnGarnrolle({
        title: displayName.trim(),
        summary: summary.trim() || undefined,
        tags: profileTags(),
        address: address.trim() || undefined,
        location: selectedLocation ?? undefined,
        map_state: visibilityChoice,
        radius_m: visibilityChoice === "radius" ? radiusM : undefined,
      });
      if (browser) {
        sessionStorage.removeItem(draftStorageKey(activeAccountId));
      }
      await invalidateAll();
      saveMessage =
        "Deine Garnrolle wurde gespeichert. Du kannst ihre Sichtbarkeit jederzeit ändern.";
      await goto("/settings#meine-garnrolle", {
        replaceState: true,
        noScroll: true,
        keepFocus: true,
      });
    } catch (error) {
      profileError = describeSaveError(error);
    } finally {
      isSaving = false;
    }
  }
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
        Du bist noch nicht angemeldet. Bei der Registrierung wird deine
        Garnrolle angelegt; nach dem Login kannst du sie hier einrichten.
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
          <p class="warn">
            Deine Sitzung ist aktiv, aber der zugehörige Garnrollen-Datensatz
            fehlt. Speichern ist deshalb gesperrt.
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

    {#if visibility.state === "not_on_map"}
      <div class="setup-guide" data-testid="garnrolle-first-user-guide">
        <p class="eyebrow">Dein Einstieg</p>
        <h3>Deine Garnrolle ist schon da.</h3>
        <p>Du brauchst keine weitere Rolle und keinen Antrag, um anzufangen.</p>
        <ol>
          <li>
            <strong>Beschreiben:</strong> Wähle einen Anzeigenamen.
          </li>
          <li>
            <strong>Verankern:</strong> Setze freiwillig einen privaten Punkt auf
            der Karte.
          </li>
          <li>
            <strong>Freigeben:</strong> Entscheide selbst, ob nichts, ein ungefährer
            Ort oder der genaue Punkt öffentlich wird.
          </li>
        </ol>
      </div>
    {/if}

    <form
      class="garnrolle-form"
      aria-describedby="my-garnrolle-save-note"
      on:submit={handleSave}
    >
      <fieldset disabled={isLoadingProfile || isSaving}>
        <legend>1. Garnrolle beschreiben</legend>
        <p class="field-intro">
          Nur der Anzeigename ist erforderlich. Alles Weitere kannst du später
          ergänzen.
        </p>
        <label>
          Anzeigename
          <input
            bind:value={displayName}
            placeholder="Meine Garnrolle"
            maxlength="160"
            required
          />
        </label>
        <label>
          Kurzbeschreibung
          <textarea
            bind:value={summary}
            rows="3"
            maxlength="2000"
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

      <fieldset disabled={isLoadingProfile || isSaving}>
        <legend>2. Privaten Kartenanker wählen</legend>
        <p class="field-intro">
          Der Kartenanker ist zunächst privat. Erst deine Auswahl im nächsten
          Schritt bestimmt, ob und wie daraus eine öffentliche Position wird.
        </p>

        <div class="location-card" data-testid="garnrolle-location-state">
          {#if selectedLocation}
            <div>
              <strong>Privater Kartenanker gewählt</strong>
              <small>
                {visibilityChoice === "not_on_map"
                  ? "Der Punkt bleibt vollständig unsichtbar."
                  : "Dieser Punkt ist die Grundlage deiner gewählten öffentlichen Darstellung."}
              </small>
            </div>
            <button
              bind:this={locationButton}
              type="button"
              class="btn"
              on:click={chooseMapLocation}
            >
              Punkt ändern
            </button>
          {:else}
            <div>
              <strong>Noch kein Kartenanker gewählt</strong>
              <small>
                Wähle den passenden Punkt selbst auf der Karte. Eine Adresse
                wird nicht automatisch in eine Position umgewandelt.
              </small>
            </div>
            <button
              bind:this={locationButton}
              type="button"
              class="btn btn-primary"
              on:click={chooseMapLocation}
              data-testid="choose-garnrolle-location"
            >
              Punkt auf Karte wählen
            </button>
          {/if}
        </div>

        <label>
          Adresse oder Ortsnotiz <span class="optional">privat, optional</span>
          <input
            bind:value={address}
            maxlength="500"
            placeholder="z. B. Stadtteil oder Treffpunkt"
          />
        </label>
      </fieldset>

      <fieldset disabled={isLoadingProfile || isSaving}>
        <legend>3. Öffentliche Sichtbarkeit wählen</legend>
        <p class="field-intro">
          Du kannst diese Entscheidung jederzeit ändern.
        </p>
        <div class="radio-group" role="radiogroup" aria-label="Sichtbarkeit">
          <label class="radio-card">
            <input
              type="radio"
              bind:group={visibilityChoice}
              value="not_on_map"
            />
            <span>
              <strong>Privat – nicht öffentlich auf der Karte</strong>
              <small
                >Ein gewählter Kartenanker bleibt gespeichert, aber unsichtbar.</small
              >
            </span>
          </label>
          <label class="radio-card">
            <input type="radio" bind:group={visibilityChoice} value="radius" />
            <span>
              <strong>Öffentlich ungefähr</strong>
              <small
                >Gezeigt wird nur eine versetzte Position innerhalb des
                gewählten Umkreises.</small
              >
            </span>
          </label>
          <label class="radio-card">
            <input type="radio" bind:group={visibilityChoice} value="exact" />
            <span>
              <strong>Öffentlich exakt</strong>
              <small>Der gewählte Kartenanker wird genau veröffentlicht.</small>
            </span>
          </label>
        </div>

        {#if visibilityChoice !== "not_on_map" && !selectedLocation}
          <p class="form-message hint" role="status">
            Für diese öffentliche Sichtbarkeit fehlt noch ein Kartenanker.
          </p>
        {/if}

        {#if visibilityChoice === "radius"}
          <label>
            Ungefährer Umkreis in Metern
            <input
              type="number"
              min="50"
              max="5000"
              step="50"
              bind:value={radiusM}
              aria-invalid={!radiusIsValid}
              aria-describedby="garnrolle-radius-help"
            />
          </label>
          <p
            id="garnrolle-radius-help"
            class={radiusIsValid
              ? "field-intro"
              : "field-intro form-message error"}
          >
            {radiusIsValid
              ? "Erlaubt sind 50 bis 5.000 Meter."
              : "Bitte wähle einen Umkreis zwischen 50 und 5.000 Metern."}
          </p>
        {/if}
      </fieldset>

      {#if !canEdit}
        <p
          class="form-message error"
          role="alert"
          data-testid="garnrolle-role-warning"
        >
          Melde dich an, um deine Garnrolle zu speichern.
        </p>
      {/if}

      {#if draftMessage}
        <p
          class="form-message hint"
          role="status"
          data-testid="garnrolle-draft-status"
        >
          {draftMessage}
        </p>
      {/if}
      {#if profileError}
        <p
          class="form-message error"
          role="alert"
          data-testid="garnrolle-error"
        >
          {profileError}
        </p>
      {/if}
      {#if saveMessage}
        <p
          class="form-message success"
          role="status"
          data-testid="garnrolle-success"
        >
          {saveMessage}
        </p>
      {/if}

      <div class="actions">
        <button
          type="submit"
          class="btn btn-primary"
          disabled={!canSave}
          data-testid="save-garnrolle"
        >
          {isSaving ? "Garnrolle wird gespeichert…" : "Garnrolle speichern"}
        </button>
      </div>
      <p id="my-garnrolle-save-note" class="muted">
        Öffentlich sind Anzeigename, Kurzbeschreibung, Fähigkeiten, Güter und
        Interessen. Adresse oder Ortsnotiz bleiben privat. Bei „Öffentlich
        exakt“ wird der Kartenanker genau gezeigt, bei „Öffentlich ungefähr“ nur
        eine versetzte Näherung und bei „Privat“ gar keine Position. Kartenanker
        und Adressnotiz werden nicht automatisch abgeglichen.
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
  .empty-card,
  .location-card,
  .setup-guide {
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
    border-radius: 12px;
    display: flex;
    gap: 1rem;
    justify-content: space-between;
    padding: 1rem;
  }

  .status-card p,
  .empty-card p,
  .setup-guide p {
    margin: 0.35rem 0 0;
  }

  .setup-guide {
    display: block;
    background: rgba(106, 166, 255, 0.08);
  }

  .setup-guide h3 {
    margin: 0.25rem 0 0;
  }

  .setup-guide ol {
    margin: 0.85rem 0 0;
    padding-left: 1.25rem;
  }

  .setup-guide li + li {
    margin-top: 0.45rem;
  }

  .location-card {
    align-items: center;
  }

  .location-card small {
    color: var(--muted, #9aa4b2);
    display: block;
    font-weight: 400;
    margin-top: 0.25rem;
    max-width: 34rem;
  }

  .warn {
    color: #ffd28a;
  }

  .muted,
  .field-intro {
    color: var(--muted, #9aa4b2);
    font-size: 0.92rem;
  }

  .field-intro {
    margin: 0;
  }

  .optional {
    color: var(--muted, #9aa4b2);
    font-size: 0.82rem;
    font-weight: 400;
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

  .form-message {
    border-radius: 8px;
    margin: 0;
    padding: 0.8rem 1rem;
  }

  .form-message.error {
    background: rgba(255, 107, 107, 0.12);
    border: 1px solid #ff6b6b;
  }

  .form-message.success {
    background: rgba(84, 225, 166, 0.12);
    border: 1px solid rgba(84, 225, 166, 0.7);
  }

  .form-message.hint {
    background: rgba(255, 210, 138, 0.08);
    border: 1px solid rgba(255, 210, 138, 0.55);
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

  .btn:focus-visible,
  input:focus-visible,
  textarea:focus-visible {
    outline: 3px solid var(--accent, #6aa6ff);
    outline-offset: 2px;
  }

  .radio-card:focus-within {
    border-color: var(--accent, #6aa6ff);
  }

  .btn:disabled,
  .btn[aria-disabled="true"] {
    cursor: not-allowed;
    opacity: 0.55;
  }

  @media (max-width: 640px) {
    .section-head,
    .status-card,
    .empty-card,
    .location-card,
    .setup-guide {
      display: grid;
    }
  }
</style>
