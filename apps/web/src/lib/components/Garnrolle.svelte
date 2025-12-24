<script lang="ts">
  export let label = 'Mein Konto';
  export let tooltip = 'Garnrolle – Konto';
</script>

<style>
  .wrap{ position:relative; display:inline-block; text-decoration: none; color: inherit; }
  .roll{
    width:34px; height:34px; border-radius:50%;
    background: radial-gradient(circle at 30% 30%, #6aa6ff 0%, #2c6de0 60%, #1b3f7a 100%);
    border:1px solid rgba(255,255,255,0.12);
    box-shadow: var(--shadow);
    display:grid; place-items:center; cursor:pointer;
    transition: transform 0.1s ease;
  }
  .roll:active { transform: scale(0.95); }
  .hole{ width:10px; height:10px; border-radius:50%; background:#0f1a2f; box-shadow: inset 0 0 8px rgba(0,0,0,.6); }
  .tip{
    position:absolute; right:0; transform:translateY(calc(-100% - 8px));
    background:var(--panel); border:1px solid var(--panel-border); color:var(--text);
    padding:6px 8px; font-size:12px; border-radius:8px; white-space:nowrap;
    opacity:0; pointer-events:none; transition:.15s ease;
  }
  .wrap:hover .tip{ opacity:1; }
  .wrap:focus-visible { outline: 2px solid var(--primary); border-radius: 50%; }
</style>

<a href="/settings" class="wrap" aria-label={label}>
  <div class="roll" title={tooltip}><div class="hole" /></div>
  <div class="tip">{tooltip}</div>
</a>
