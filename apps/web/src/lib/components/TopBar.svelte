<script lang="ts">
  import Garnrolle from './Garnrolle.svelte';
  import AuthStatus from '$lib/auth/AuthStatus.svelte';
  import { contextPanelOpen } from '$lib/stores/uiView';
</script>

<style>
  .topbar{
    position:absolute; inset:0 0 auto 0; min-height:52px; z-index:41;
    display:flex; align-items:center; gap:8px; padding:0 12px;
    padding:env(safe-area-inset-top) 12px 0 12px;
    background: linear-gradient(180deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
    pointer-events: none;
    transition: right 0.3s ease-in-out;
  }

  .spacer{ flex:1; pointer-events: none; }

  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
    pointer-events: auto;
  }

  /* Desktop: adjust layout slightly to avoid overlapping ContextPanel */
  @media (min-width: 769px) {
    .topbar.panel-open {
      right: var(--context-panel-width, 400px); /* leaves room for ContextPanel */
    }
  }
</style>

<div class="topbar" class:panel-open={$contextPanelOpen} role="toolbar" aria-label="Navigation">
  <div class="spacer"></div>
  <div class="actions">
    <AuthStatus />
    <Garnrolle />
  </div>
</div>
