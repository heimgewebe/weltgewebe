#!/usr/bin/env node
import { resolve } from "node:path";
import {
  assertExactGitCheckout,
  defaultEvidencePath,
  readAndValidateWebRuntimeEvidence,
} from "./web-runtime-evidence.mjs";

const revision = process.env.GIT_COMMIT_SHA ?? process.env.GITHUB_SHA ?? "";
if (!/^[0-9a-f]{40}$/.test(revision)) {
  throw new Error(
    "GIT_COMMIT_SHA or GITHUB_SHA must contain the exact lowercase commit SHA",
  );
}
assertExactGitCheckout({ revision });
const path = process.env.WELTGEWEBE_WEB_RUNTIME_EVIDENCE_PATH
  ? resolve(process.env.WELTGEWEBE_WEB_RUNTIME_EVIDENCE_PATH)
  : defaultEvidencePath(revision);
const evidence = readAndValidateWebRuntimeEvidence(path, revision);
console.log(
  JSON.stringify(
    {
      kind: evidence.kind,
      source_revision: evidence.source_revision,
      profiles: Object.fromEntries(
        Object.entries(evidence.profiles).map(([profileId, profile]) => [
          profileId,
          {
            runs: profile.runs,
            aggregates: profile.aggregates,
          },
        ]),
      ),
      enforcement: "measurement_integrity_only",
      thresholds_blocking: false,
    },
    null,
    2,
  ),
);
