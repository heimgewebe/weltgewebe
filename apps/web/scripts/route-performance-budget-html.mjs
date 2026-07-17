function findTagEnd(html, start) {
  let quote = null;
  for (let index = start; index < html.length; index += 1) {
    const character = html[index];
    if (quote) {
      if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
    } else if (character === ">") {
      return index;
    }
  }
  throw new Error("Unterminated HTML tag starting at byte " + start);
}

function extractLinkTags(html) {
  const lowerHtml = html.toLowerCase();
  const tags = [];
  let cursor = 0;
  while (cursor < html.length) {
    const nextOpen = lowerHtml.indexOf("<", cursor);
    if (nextOpen === -1) break;
    if (lowerHtml.startsWith("<!--", nextOpen)) {
      const commentEnd = lowerHtml.indexOf("-->", nextOpen + 4);
      if (commentEnd === -1) {
        throw new Error(
          "Unterminated HTML comment starting at byte " + nextOpen,
        );
      }
      cursor = commentEnd + 3;
      continue;
    }
    const scriptBoundary = lowerHtml[nextOpen + 7];
    const styleBoundary = lowerHtml[nextOpen + 6];
    const isScript =
      lowerHtml.startsWith("<script", nextOpen) &&
      (scriptBoundary === undefined || /[\s/>]/.test(scriptBoundary));
    const isStyle =
      lowerHtml.startsWith("<style", nextOpen) &&
      (styleBoundary === undefined || /[\s/>]/.test(styleBoundary));
    if (isScript || isStyle) {
      const name = isScript ? "script" : "style";
      const openEnd = findTagEnd(html, nextOpen);
      const closeStart = lowerHtml.indexOf("</" + name, openEnd + 1);
      if (closeStart === -1) {
        throw new Error("Unterminated <" + name + "> element");
      }
      cursor = findTagEnd(html, closeStart) + 1;
      continue;
    }
    if (lowerHtml.startsWith("<link", nextOpen)) {
      const boundary = lowerHtml[nextOpen + 5];
      if (boundary === undefined || /[\s/>]/.test(boundary)) {
        const end = findTagEnd(html, nextOpen);
        tags.push(html.slice(nextOpen, end + 1));
        cursor = end + 1;
        continue;
      }
    }
    cursor = nextOpen + 1;
  }
  return tags;
}

function parseTagAttributes(tag) {
  const attributes = new Map();
  let index = 5;
  const limit = tag.length - 1;
  while (index < limit) {
    while (index < limit && /\s/.test(tag[index])) index += 1;
    if (index >= limit || tag[index] === "/") break;

    const nameStart = index;
    while (index < limit && !/[\s=/>]/.test(tag[index])) index += 1;
    if (nameStart === index) {
      throw new Error("Malformed <link> attribute near byte " + index);
    }
    const name = tag.slice(nameStart, index).toLowerCase();
    while (index < limit && /\s/.test(tag[index])) index += 1;

    let value = "";
    if (tag[index] === "=") {
      index += 1;
      while (index < limit && /\s/.test(tag[index])) index += 1;
      if (index >= limit) {
        throw new Error("Missing value for <link> attribute " + name);
      }
      const quote =
        tag[index] === '"' || tag[index] === "'" ? tag[index] : null;
      if (quote) {
        index += 1;
        const valueStart = index;
        while (index < limit && tag[index] !== quote) index += 1;
        if (index >= limit) {
          throw new Error("Unterminated quoted <link> attribute " + name);
        }
        value = tag.slice(valueStart, index);
        index += 1;
      } else {
        const valueStart = index;
        while (index < limit && !/[\s>]/.test(tag[index])) index += 1;
        value = tag.slice(valueStart, index);
        if (value.length === 0) {
          throw new Error("Missing value for <link> attribute " + name);
        }
      }
    }
    if (attributes.has(name)) {
      throw new Error("Duplicate <link> attribute " + name);
    }
    attributes.set(name, value);
  }
  return attributes;
}

function isExternalReference(reference) {
  return (
    reference.startsWith("//") || /^[A-Za-z][A-Za-z0-9+.-]*:/.test(reference)
  );
}

export function collectInitialAssetReferences(html) {
  const references = [];
  const seen = new Set();
  for (const tag of extractLinkTags(html)) {
    const attributes = parseTagAttributes(tag);
    const rel = attributes.get("rel");
    const href = attributes.get("href");
    if (!rel || !href) continue;
    const relTokens = rel.toLowerCase().split(/\s+/);
    if (
      !relTokens.includes("modulepreload") &&
      !relTokens.includes("stylesheet")
    ) {
      continue;
    }
    if (isExternalReference(href)) {
      throw new Error(
        "External initial asset cannot be measured by the local budget: " +
          href,
      );
    }
    const cleanHref = href.split(/[?#]/, 1)[0];
    if (!cleanHref || seen.has(cleanHref)) continue;
    seen.add(cleanHref);
    references.push(cleanHref);
  }
  return references;
}
