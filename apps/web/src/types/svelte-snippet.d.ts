// Minimal Snippet type to align SvelteKit's generated types with Svelte 4.
declare module "svelte" {
  export type Snippet<Props = Record<string, unknown>> = (
    props: Props,
  ) => unknown;
}
