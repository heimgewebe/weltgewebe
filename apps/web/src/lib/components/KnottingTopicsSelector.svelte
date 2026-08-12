<script lang="ts">
  import {
    KNOTTING_TOPICS,
    MAX_KNOTTING_TOPICS,
    toggleKnottingTopic,
    type KnottingTopic,
  } from "$lib/knottingTopics";

  interface Props {
    value?: KnottingTopic[];
    disabled?: boolean;
    id?: string;
  }

  let {
    value = $bindable([]),
    disabled = false,
    id = "knotting-topics",
  }: Props = $props();

  function toggle(topic: KnottingTopic) {
    value = toggleKnottingTopic(value, topic);
  }
</script>

<fieldset class="topic-fieldset" aria-describedby={`${id}-help`}>
  <legend>Themen <span class="optional">(bis zu 4)</span></legend>
  <p id={`${id}-help`} class="topic-help">
    Themen ordnen den Knoten ein und bestimmen seine Farben im Gewebe.
  </p>
  <div class="topic-options">
    {#each KNOTTING_TOPICS as topic}
      {@const isSelected = value.includes(topic)}
      <button
        type="button"
        class="topic-option"
        class:topic-selected={isSelected}
        aria-pressed={isSelected}
        disabled={disabled ||
          (!isSelected && value.length >= MAX_KNOTTING_TOPICS)}
        onclick={() => toggle(topic)}
      >
        {topic}
      </button>
    {/each}
  </div>
  <p class="topic-count">
    {value.length}/{MAX_KNOTTING_TOPICS} ausgewählt
  </p>
</fieldset>

<style>
  .topic-fieldset {
    min-inline-size: 0;
    margin: 0 0 1.25rem;
    padding: 0;
    border: 0;
  }

  .topic-fieldset legend {
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: var(--text, #e9eef5);
  }

  .optional,
  .topic-help,
  .topic-count {
    color: var(--muted, #9aa4b2);
    font-size: 0.85rem;
  }

  .optional {
    font-weight: 400;
  }

  .topic-help {
    margin: 0 0 0.75rem;
  }

  .topic-options {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .topic-option {
    min-height: 44px;
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.06));
    border-radius: 999px;
    background: var(--bg, #0f1115);
    color: var(--text, #e9eef5);
    font: inherit;
    cursor: pointer;
  }

  .topic-option:hover:not(:disabled),
  .topic-option.topic-selected {
    border-color: var(--accent, #6aa6ff);
  }

  .topic-option.topic-selected {
    background: var(--accent-soft, rgba(106, 166, 255, 0.18));
  }

  .topic-option:focus-visible {
    outline: 2px solid var(--accent, #6aa6ff);
    outline-offset: 2px;
  }

  .topic-option:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .topic-option.topic-selected:disabled {
    opacity: 0.75;
  }

  .topic-count {
    margin: 0.55rem 0 0;
  }
</style>
