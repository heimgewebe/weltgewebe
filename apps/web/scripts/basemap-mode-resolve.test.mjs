import assert from "node:assert/strict";
import { test } from "node:test";
import {
  assertVercelLocalBasemapDelivery,
  resolveBasemapModeForBuild,
} from "./basemap-mode-resolve.mjs";

const allowed = ["local-sovereign", "remote-style"];

test("Vercel + no explicit mode -> remote-style", () => {
  const result = resolveBasemapModeForBuild({
    rawMode: "",
    defaultMode: "local-sovereign",
    allowedModes: allowed,
    isVercel: true,
  });
  assert.deepEqual(result, { ok: true, mode: "remote-style" });
});

test("explicit local-sovereign on Vercel stays local", () => {
  const result = resolveBasemapModeForBuild({
    rawMode: "local-sovereign",
    defaultMode: "local-sovereign",
    allowedModes: allowed,
    isVercel: true,
  });
  assert.deepEqual(result, { ok: true, mode: "local-sovereign" });
});

test("non-Vercel + no mode stays policy default", () => {
  const result = resolveBasemapModeForBuild({
    rawMode: undefined,
    defaultMode: "local-sovereign",
    allowedModes: allowed,
    isVercel: false,
  });
  assert.deepEqual(result, { ok: true, mode: "local-sovereign" });
});

test("invalid explicit mode fails closed", () => {
  const result = resolveBasemapModeForBuild({
    rawMode: "planet",
    defaultMode: "local-sovereign",
    allowedModes: allowed,
    isVercel: true,
  });
  assert.equal(result.ok, false);
});

test("Vercel local-sovereign without delivered style fails", () => {
  const result = assertVercelLocalBasemapDelivery({
    mode: "local-sovereign",
    isVercel: true,
    styleDelivered: false,
    stylePath: "/local-basemap/style.json",
  });
  assert.equal(result.ok, false);
});

test("Vercel remote-style does not require local style delivery", () => {
  const result = assertVercelLocalBasemapDelivery({
    mode: "remote-style",
    isVercel: true,
    styleDelivered: false,
    stylePath: "/local-basemap/style.json",
  });
  assert.deepEqual(result, { ok: true });
});
