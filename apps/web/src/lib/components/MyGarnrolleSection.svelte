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
  let saveMessage: string | null = null;

  $: ownGarnrolle = findOwnGarnrolle(accounts, $authStore.account_id);
  $: visibility = describeGarnrolleVisibility(ownGarnrolle);
  $: activeAccountId =
    $authStore.authenticated && $authStore.account_id
      ? $authStore.account_id
      : null;
  $: canEdit = $authStore.role === "weber" || $authStore.role === "admin";
  $: canSave =
    canEdit &&
    !!ownGarnrolle &&
    !!displayName.trim() &&
    !isLoadingProfile &&
    !isSaving &&
    (visibilityChoice === "not_on_map" ||
      (!!address.trim() && selectedLocation !== null));
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
    isLoadingProfile = true;
    profileError = null;
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
        saveMessage =
          "Ort übernommen. Prüfe Adresse und Sichtbarkeit und speichere anschließend.";
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
        return "Bitte prüfe Name, Adresse, Ort und Sichtbarkeit.";
      }
    }
    return "Die Garnrolle konnte nicht gespeichert werden. Bitte versuche es erneut.";
  }

  async function handleSave(event: SubmitEvent) {
    event.preventDefault();
    profileError = null;
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
      saveMessage = "Deine Garnrolle wurde gespeichert.";
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

    <form
      class="garnrolle-form"
      aria-describedby="my-garnrolle-save-note"
      on:submit={handleSave}
    >
      <fieldset disabled={isLoadingProfile || isSaving}>
        <legend>Garnrolle beschreiben</legend>
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
        <legend>Garnrolle auf Karte setzen</legend>
        <label>
          Adresse
          <input
            bind:value={address}
            maxlength="500"
            placeholder="Straße, Hausnummer, Ort"
          />
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
              <small>Der von dir gewählte Ort wird öffentlich sichtbar.</small>
            </span>
          </label>
          <label class="radio-card">
            <input type="radio" bind:group={visibilityChoice} value="radius" />
            <span>
              <strong>Im Umkreis sichtbar</strong>
              <small>
                Die öffentliche Position wird innerhalb des gewählten Umkreises
                versetzt.
              </small>
            </span>
          </label>
        </div>

        {#if visibilityChoice !== "not_on_map"}
          <div class="location-card" data-testid="garnrolle-location-state">
            {#if selectedLocation}
              <div>
                <strong>Ort gewählt</strong>
                <small>Die genaue Position ist auf der Karte gesetzt.</small>
              </div>
              <button type="button" class="btn" on:click={chooseMapLocation}>
                Ort ändern
              </button>
            {:else}
              <div>
                <strong>Noch kein Ort gewählt</strong>
                <small>
                  Die Adresse wird nicht automatisch in eine Position
                  umgewandelt. Wähle den passenden Punkt selbst auf der Karte.
                </small>
              </div>
              <button
                type="button"
                class="btn btn-primary"
                on:click={chooseMapLocation}
                data-testid="choose-garnrolle-location"
              >
                Ort auf Karte wählen
              </button>
            {/if}
          </div>
        {/if}

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

      {#if !canEdit}
        <p
          class="form-message error"
          role="alert"
          data-testid="garnrolle-role-warning"
        >
          Dein Konto besitzt noch keine Weber-Berechtigung. Die Garnrolle kann
          deshalb nicht gespeichert werden.
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
          {isSaving ? "Wird gespeichert…" : "Speichern"}
        </button>
        <a class="btn" href="/map?compose=node">Ersten Knoten knüpfen</a>
      </div>
      <p id="my-garnrolle-save-note" class="muted">
        Öffentlich sind Anzeigename, Kurzbeschreibung, Fähigkeiten, Güter und
        Interessen. Deine Adresse bleibt privat. Bei „Exakt sichtbar“ ist der
        gewählte Ort öffentlich; bei „Im Umkreis sichtbar“ nur eine
        versetzte Näherung; bei „Noch nicht auf der Karte“ keine Position.
        Adresse und Ort werden nicht automatisch abgeglichen.
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
  .location-card {
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
    .empty-card,
    .location-card {
      display: grid;
    }
  }
</style>
