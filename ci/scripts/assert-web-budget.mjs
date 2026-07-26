#!/usr/bin/env node
import {
  loadPerformanceContract,
  repositoryRoot,
} from "../../apps/web/scripts/performance-contract.mjs";

const contract = loadPerformanceContract({
  enforceLegacyAbsence: true,
  root: repositoryRoot,
});
const webBuild = contract.measurements.web_build;
const webRuntime = contract.measurements.web_runtime;
const apiRuntime = contract.measurements.api_runtime;

if (webBuild.status !== "blocking") {
  throw new Error("The generated web-build measurement must remain blocking");
}
if (webRuntime.status === "blocking") {
  throw new Error(
    "Web runtime thresholds cannot block until a revision-bound calibration artifact exists",
  );
}
if (apiRuntime.status === "blocking") {
  throw new Error(
    "API runtime thresholds cannot block until a revision-bound workload artifact exists",
  );
}

console.log(
  [
    "Canonical performance contract validated:",
    contract.contract_id,
    "web-build=" + webBuild.status,
    "web-runtime=" + webRuntime.status,
    "api-runtime=" + apiRuntime.status,
  ].join(" "),
);
