#!/usr/bin/env node
import { resolve } from "node:path";
import {
  assertExactGitCheckout,
  resolveExactSourceRevision,
  defaultEvidencePath,
  readAndValidateWebRuntimeEvidence,
} from "./web-runtime-evidence.mjs";

const revision = resolveExactSourceRevision();
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
