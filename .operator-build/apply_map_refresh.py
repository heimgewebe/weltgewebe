from pathlib import Path

path = Path.cwd() / "apps/web/src/routes/map/+page.svelte"
text = path.read_text()
old = '''  import { page } from "$app/stores";
'''
new = '''  import { page } from "$app/stores";
  import { invalidateAll } from "$app/navigation";
'''
assert text.count(old) == 1
text = text.replace(old, new)
old = '''  function handleRelatedSelect(
    event: CustomEvent<{ type: "node" | "garnrolle"; id: string }>,
  ) {
    const related = markersData.find(
      (item) => item.id === event.detail.id && item.type === event.detail.type,
    );
    if (related) focusAndFlyToPoint(related);
  }

'''
new = old + '''  async function handleDomainChanged() {
    leaveToNavigation();
    await invalidateAll();
  }

'''
assert text.count(old) == 1
text = text.replace(old, new)
old = '''  <ContextPanel on:selectRelated={handleRelatedSelect} />
'''
new = '''  <ContextPanel
    on:selectRelated={handleRelatedSelect}
    on:domainChanged={handleDomainChanged}
  />
'''
assert text.count(old) == 1
path.write_text(text.replace(old, new))
