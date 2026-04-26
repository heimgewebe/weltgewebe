import { readFile } from "fs/promises";
import { resolve } from "path";
import Ajv from "ajv";
import addFormats from "ajv-formats";
import { fileURLToPath } from "url";

// Since we execute this via `tsx` (pnpm exec tsx scripts/verify-demo-data.js),
// we can import the TypeScript source file directly.
import { demoNodes, demoAccounts, demoEdges } from "../apps/web/src/lib/demo/demoData";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const ROOT = resolve(__dirname, "../");

async function loadSchema(name) {
  const path = resolve(ROOT, `contracts/domain/${name}.schema.json`);
  return JSON.parse(await readFile(path, "utf-8"));
}

// Domain projections: strip UI/demo-only fields before validating against
// domain contracts. Demo data may carry UI-enriched fields (e.g. modules)
// that are not part of the domain contract.
const DOMAIN_NODE_KEYS = new Set(["id", "kind", "title", "created_at", "updated_at", "info", "summary", "tags", "location"]);
const DOMAIN_ACCOUNT_KEYS = new Set(["id", "type", "mode", "title", "summary", "location", "public_pos", "radius_m", "tags", "created_at"]);
const DOMAIN_EDGE_KEYS = new Set(["id", "source_type", "source_id", "target_type", "target_id", "edge_kind", "created_at", "expires_at", "note"]);

function project(keys: Set<string>) {
  return (obj: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(obj).filter(([k]) => keys.has(k)));
}

const toDomainNode = project(DOMAIN_NODE_KEYS);
const toDomainAccount = project(DOMAIN_ACCOUNT_KEYS);
const toDomainEdge = project(DOMAIN_EDGE_KEYS);

async function validate() {
  console.log("🔍 Validating Demo Data against Contracts (Source)...");

  const ajv = new Ajv({ strict: false });
  addFormats(ajv);

  const schemas = {
    node: await loadSchema("node"),
    account: await loadSchema("account"),
    edge: await loadSchema("edge"),
  };

  const validators = {
    node: ajv.compile(schemas.node),
    account: ajv.compile(schemas.account),
    edge: ajv.compile(schemas.edge),
  };

  let hasError = false;

  console.log(`   Checking ${demoNodes.length} nodes...`);
  demoNodes.forEach((item, i) => {
    const projected = toDomainNode(item as Record<string, unknown>);
    if (!validators.node(projected)) {
      console.error(`❌ Node[${i}] invalid:`, validators.node.errors);
      hasError = true;
    }
  });

  console.log(`   Checking ${demoAccounts.length} accounts...`);
  demoAccounts.forEach((item, i) => {
    const projected = toDomainAccount(item as Record<string, unknown>);
    if (!validators.account(projected)) {
      console.error(`❌ Account[${i}] invalid:`, validators.account.errors);
      hasError = true;
    }
  });

  console.log(`   Checking ${demoEdges.length} edges...`);
  demoEdges.forEach((item, i) => {
    const projected = toDomainEdge(item as Record<string, unknown>);
    if (!validators.edge(projected)) {
      console.error(`❌ Edge[${i}] invalid:`, validators.edge.errors);
      hasError = true;
    }
  });

  if (hasError) {
    console.error("\n💥 Validation FAILED. Demo data does not match Contracts.");
    process.exit(1);
  } else {
    console.log("\n✅ All Demo Data valid.");
  }
}

validate().catch(e => {
  console.error(e);
  process.exit(1);
});
