<script lang="ts">
  import type { ProposalDetail } from "$lib/api/governance";
  import { deriveProposalProcess } from "./proposalProcess";

  interface Props {
    proposal: ProposalDetail;
    messageCount?: number;
  }

  let { proposal, messageCount = 0 }: Props = $props();

  let process = $derived(deriveProposalProcess(proposal, messageCount));
</script>

<section
  class="process-card"
  aria-labelledby="proposal-process-heading"
  data-testid="proposal-process"
>
  <div class="heading-row">
    <p class="eyebrow">Verfahrensstand</p>
    <h2 id="proposal-process-heading">Ablauf dieses Antrags</h2>
  </div>

  <p class="summary">{process.summary}</p>

  {#if process.deadlineAt && process.deadlineLabel}
    <p class="deadline">
      <span>{process.deadlineLabel}</span>
      <time datetime={process.deadlineAt}>
        {new Date(process.deadlineAt).toLocaleString("de-DE")}
      </time>
    </p>
  {/if}

  <ol class="steps" aria-label="Ablauf des Weberantrags">
    {#each process.steps as step, index}
      <li
        class:complete={step.state === "complete"}
        class:current={step.state === "current"}
        class:upcoming={step.state === "upcoming"}
        aria-current={step.state === "current" ? "step" : undefined}
        aria-label={`${step.label}: ${step.state === "complete" ? "abgeschlossen" : step.state === "current" ? "aktuell" : "steht noch aus"}`}
        data-testid={`proposal-process-step-${step.id}`}
      >
        <span class="marker" aria-hidden="true">
          {step.state === "complete" ? "✓" : index + 1}
        </span>
        <span>{step.label}</span>
      </li>
    {/each}
  </ol>

  <dl class="facts">
    <div data-testid="proposal-process-vetoes">
      <dt>Begründete Vetos</dt>
      <dd>{process.vetoCount}</dd>
    </div>
    <div data-testid="proposal-process-messages">
      <dt>Gesprächsbeiträge</dt>
      <dd>{process.messageCount}</dd>
    </div>
    {#if process.showVotes}
      <div data-testid="proposal-process-votes">
        <dt>Abgegebene Stimmen</dt>
        <dd>{process.voteCount}</dd>
      </div>
    {/if}
  </dl>
</section>

<style>
  .process-card {
    border: 1px solid var(--panel-border);
    border-radius: 18px;
    background: var(--panel);
    padding: 22px;
    margin-top: 16px;
  }
  .heading-row {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .eyebrow {
    margin: 0 0 4px;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-size: 0.72rem;
    font-weight: 750;
    color: var(--accent);
  }
  h2 {
    margin: 0;
  }
  .summary {
    max-width: 68ch;
    margin: 18px 0 0;
    color: var(--muted);
    line-height: 1.55;
  }
  .deadline {
    display: flex;
    flex-wrap: wrap;
    gap: 5px 10px;
    margin: 14px 0 0;
    font-size: 0.9rem;
  }
  .deadline span {
    color: var(--muted);
  }
  .deadline time {
    font-weight: 720;
  }
  .steps {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 10px;
    padding: 0;
    margin: 22px 0 0;
    list-style: none;
  }
  .steps li {
    display: flex;
    align-items: center;
    gap: 9px;
    min-width: 0;
    border-radius: 12px;
    background: var(--panel-solid);
    padding: 11px;
    color: var(--muted);
    font-size: 0.84rem;
    font-weight: 700;
  }
  .steps li.complete {
    color: var(--accent);
  }
  .steps li.current {
    background: var(--accent-soft);
    color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .steps li.upcoming {
    opacity: 0.72;
  }
  .marker {
    display: grid;
    flex: 0 0 28px;
    width: 28px;
    height: 28px;
    place-items: center;
    border: 1px solid currentColor;
    border-radius: 50%;
    font-size: 0.78rem;
  }
  .facts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 8px;
    margin: 18px 0 0;
  }
  .facts div {
    border-radius: 12px;
    background: var(--panel-solid);
    padding: 10px;
  }
  dt {
    color: var(--muted);
    font-size: 0.76rem;
  }
  dd {
    margin: 3px 0 0;
    font-weight: 760;
  }
  @media (max-width: 620px) {
    .steps {
      grid-template-columns: 1fr;
    }
  }
</style>
