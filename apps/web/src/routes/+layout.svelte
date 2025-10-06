<script lang="ts">
        import type { Snippet } from 'svelte';
        import favicon from '$lib/assets/favicon.svg';

        type LayoutData = {
                canonical?: string;
        };

        let { data, children } = $props<{ data?: LayoutData; children?: Snippet }>();
</script>

<svelte:head>
        <link rel="icon" href={favicon} />
        {#if data?.canonical}
                <link rel="canonical" href={data.canonical} />
        {/if}
</svelte:head>

{@render children?.()}
