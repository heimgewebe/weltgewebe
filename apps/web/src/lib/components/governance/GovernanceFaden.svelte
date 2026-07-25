<script lang="ts">
  import type { ProposalDetail, ProposalMessage } from "$lib/api/governance";
  import {
    deriveGovernanceFadenSummary,
    visibleStrandOffsets,
  } from "./governanceFaden";

  export let proposal: ProposalDetail;
  export let messages: ProposalMessage[] = [];

  $: summary = deriveGovernanceFadenSummary(proposal, messages);

  function curve(
    x1: number,
    y1: number,
    x2: number,
    y2: number,
    offset: number,
  ): string {
    const middleX = (x1 + x2) / 2;
    const middleY = (y1 + y2) / 2 + offset;
    return `M ${x1} ${y1} Q ${middleX} ${middleY} ${x2} ${y2}`;
  }
</script>

<section
  class="faden-card"
  aria-labelledby="governance-faden-heading"
  data-testid="governance-faden"
>
  <div class="heading-row">
    <div>
      <p class="eyebrow">Abgeleitete Darstellung</p>
      <h2 id="governance-faden-heading">Fäden dieses Antrags</h2>
    </div>
    <strong>{summary.total} {summary.total === 1 ? "Faden" : "Fäden"}</strong>
  </div>

  <p class="explanation">
    Diese Fäden werden aus den belegten Webungsaktionen berechnet. Sie können
    weder angelegt noch bearbeitet oder gelöscht werden.
  </p>

  <figure>
    <svg
      viewBox="0 0 720 400"
      role="img"
      aria-label={`Antragsgewebe mit ${summary.total} abgeleiteten Fäden`}
      preserveAspectRatio="xMidYMid meet"
    >
      <g class="threads applicant-threads">
        {#each visibleStrandOffsets(summary.proposal) as offset}
          <path d={curve(148, 82, 326, 196, offset)} />
        {/each}
      </g>
      <g class="threads veto-threads">
        {#each visibleStrandOffsets(summary.vetoes) as offset}
          <path d={curve(572, 82, 394, 196, offset)} />
        {/each}
      </g>
      <g class="threads message-threads">
        {#each visibleStrandOffsets(summary.messages) as offset}
          <path d={curve(148, 318, 326, 204, offset)} />
        {/each}
      </g>
      <g class="threads vote-threads">
        {#each visibleStrandOffsets(summary.votes) as offset}
          <path d={curve(572, 318, 394, 204, offset)} />
        {/each}
      </g>

      <g class="endpoint applicant-endpoint">
        <circle cx="112" cy="64" r="38" />
        <text x="112" y="60">Antrag</text>
        <text class="count" x="112" y="78">1</text>
      </g>
      <g class="endpoint veto-endpoint" class:inactive={summary.vetoes === 0}>
        <circle cx="608" cy="64" r="38" />
        <text x="608" y="60">Vetos</text>
        <text class="count" x="608" y="78">{summary.vetoes}</text>
      </g>
      <g
        class="endpoint message-endpoint"
        class:inactive={summary.messages === 0}
      >
        <circle cx="112" cy="336" r="38" />
        <text x="112" y="332">Gespräch</text>
        <text class="count" x="112" y="350">{summary.messages}</text>
      </g>
      <g class="endpoint vote-endpoint" class:inactive={summary.votes === 0}>
        <circle cx="608" cy="336" r="38" />
        <text x="608" y="332">Stimmen</text>
        <text class="count" x="608" y="350">{summary.votes}</text>
      </g>

      <g class="proposal-node">
        <circle cx="360" cy="200" r="54" />
        <text x="360" y="194">Antrag</text>
        <text class="proposal-title" x="360" y="214">
          {proposal.applicant_title}
        </text>
      </g>
    </svg>

    <figcaption>
      Der Antrag steht im Zentrum. Die vier Fadenbündel zeigen Antragstellung,
      Vetos, Gesprächsbeiträge und abgegebene Stimmen.
    </figcaption>
  </figure>

  <dl class="faden-counts">
    <div data-testid="faden-count-proposal">
      <dt>Antrag gestellt</dt>
      <dd>{summary.proposal}</dd>
    </div>
    <div data-testid="faden-count-vetoes">
      <dt>Vetos</dt>
      <dd>{summary.vetoes}</dd>
    </div>
    <div data-testid="faden-count-messages">
      <dt>Gesprächsbeiträge</dt>
      <dd>{summary.messages}</dd>
    </div>
    <div data-testid="faden-count-votes">
      <dt>Stimmen</dt>
      <dd>{summary.votes}</dd>
    </div>
  </dl>
</section>

<style>
  .faden-card {
    border: 1px solid var(--panel-border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    padding: 22px;
    margin-top: 16px;
    overflow: hidden;
    box-shadow: 0 16px 54px rgba(0, 0, 0, 0.2);
  }
  .heading-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
  }
  .heading-row strong {
    white-space: nowrap;
    border-radius: 999px;
    background: var(--success-soft);
    color: var(--success);
    padding: 7px 11px;
  }
  .eyebrow {
    margin: 0 0 4px;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-size: 0.72rem;
    font-weight: 750;
    color: var(--success);
  }
  h2 {
    margin: 0;
  }
  .explanation,
  figcaption {
    color: var(--muted);
    line-height: 1.5;
  }
  figure {
    margin: 18px 0 0;
  }
  svg {
    display: block;
    width: 100%;
    max-height: 420px;
  }
  .threads path {
    fill: none;
    stroke-width: 2.5;
    stroke-linecap: round;
    opacity: 0.82;
  }
  .applicant-threads path {
    stroke: var(--success);
  }
  .veto-threads path {
    stroke: var(--danger);
  }
  .message-threads path {
    stroke: var(--accent);
  }
  .vote-threads path {
    stroke: var(--notice);
  }
  .endpoint circle,
  .proposal-node circle {
    fill: var(--surface-raised);
    stroke: var(--panel-border-strong);
    stroke-width: 2;
  }
  .endpoint.inactive {
    opacity: 0.42;
  }
  text {
    text-anchor: middle;
    font-family: system-ui, sans-serif;
    font-size: 12px;
    font-weight: 700;
    fill: var(--text);
  }
  text.count {
    font-size: 14px;
  }
  .proposal-node circle {
    fill: var(--accent);
    stroke: #91bdff;
  }
  .proposal-node text {
    fill: #09111d;
  }
  .proposal-title {
    font-size: 10px;
    font-weight: 650;
  }
  figcaption {
    margin-top: 8px;
    font-size: 0.9rem;
  }
  .faden-counts {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
    margin: 18px 0 0;
  }
  .faden-counts div {
    border: 1px solid var(--panel-border);
    border-radius: var(--radius);
    background: rgba(255, 255, 255, 0.035);
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
    .heading-row {
      flex-direction: column;
    }
    .faden-counts {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
