/**
 * Minimal DOM element tree for Vitest (node environment).
 *
 * Supports the createElement / text / attribute / custom-property path used by
 * weaveRuntime. Intentionally test-only: production code never imports this.
 */
export class DomElement {
  className = "";
  title = "";
  textContent = "";
  style = {
    opacity: "",
    background: "",
    props: new Map<string, string>(),
    setProperty(name: string, value: string) {
      this.props.set(name, value);
    },
    getPropertyValue(name: string) {
      return this.props.get(name) ?? "";
    },
  };
  dataset: Record<string, string> = {};
  children: DomElement[] = [];
  attributes = new Map<string, string>();
  tagName = "SPAN";

  setAttribute(name: string, value: string) {
    this.attributes.set(name, value);
    if (name.startsWith("data-")) {
      const key = name
        .slice(5)
        .replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase());
      this.dataset[key] = value;
    }
  }

  getAttribute(name: string) {
    return this.attributes.get(name) ?? null;
  }

  append(...nodes: DomElement[]) {
    this.children.push(...nodes);
  }

  get firstChild(): DomElement | null {
    return this.children[0] ?? null;
  }

  removeChild(child: DomElement) {
    const index = this.children.indexOf(child);
    if (index >= 0) this.children.splice(index, 1);
    return child;
  }

  querySelectorAll(selector: string): DomElement[] {
    const matches: DomElement[] = [];
    const visit = (node: DomElement) => {
      for (const child of node.children) {
        if (selector === "*" || matchesSelector(child, selector)) {
          matches.push(child);
        }
        visit(child);
      }
    };
    visit(this);
    return matches;
  }
}

function matchesSelector(node: DomElement, selector: string): boolean {
  if (selector === "*") return true;
  if (selector.startsWith(".")) {
    return node.className.split(/\s+/).includes(selector.slice(1));
  }
  if (selector.startsWith("[") && selector.endsWith("]")) {
    const body = selector.slice(1, -1);
    const eq = body.indexOf("=");
    if (eq < 0) return node.attributes.has(body);
    const name = body.slice(0, eq);
    const raw = body.slice(eq + 1).replace(/^["']|["']$/g, "");
    return node.attributes.get(name) === raw;
  }
  return false;
}

/** Install a document.createElement stub that yields {@link DomElement}. */
export function installDom(vi: {
  stubGlobal: (name: string, value: unknown) => void;
}): void {
  vi.stubGlobal("document", {
    createElement: () => new DomElement(),
  });
}
