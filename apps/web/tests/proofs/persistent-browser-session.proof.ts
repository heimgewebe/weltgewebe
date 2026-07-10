import { chromium, expect, test, type BrowserContext, type Page } from "@playwright/test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

interface AuthStatus {
  authenticated: boolean;
  account_id?: string;
  role: string;
}

async function getAuthStatus(page: Page): Promise<AuthStatus> {
  return page.evaluate(async () => {
    const response = await fetch("/api/auth/me", { credentials: "include" });
    if (!response.ok) throw new Error(`auth status failed: ${response.status}`);
    return response.json();
  });
}

async function loginWithProofSession(
  context: BrowserContext,
  baseURL: string,
): Promise<string> {
  const response = await context.request.post(
    `${baseURL}/api/auth/testing/passkeys/bootstrap-session`,
  );
  if (!response.ok()) {
    throw new Error(
      `proof session bootstrap failed: ${response.status()} ${await response.text()}`,
    );
  }
  const body = (await response.json()) as { account_id?: string };
  if (!body.account_id) {
    throw new Error("proof session bootstrap returned no account_id");
  }
  return body.account_id;
}

test("session is shared by normal windows, survives restart, and stays profile-local", async ({
  baseURL,
}) => {
  if (!baseURL) throw new Error("baseURL is required");

  const profileDir = await mkdtemp(join(tmpdir(), "weltgewebe-session-proof-"));
  let persistentContext = await chromium.launchPersistentContext(profileDir);
  let isolatedBrowser: Awaited<ReturnType<typeof chromium.launch>> | undefined;

  const proof = {
    same_profile_second_window: false,
    browser_restart: false,
    isolated_profile: false,
    persistent_cookie: false,
    logout_propagation: false,
  };

  try {
    const firstPage = persistentContext.pages()[0] ?? (await persistentContext.newPage());
    await firstPage.goto(baseURL);
    const accountId = await loginWithProofSession(persistentContext, baseURL);
    await expect.poll(() => getAuthStatus(firstPage)).toMatchObject({
      authenticated: true,
      account_id: accountId,
    });

    const sessionCookie = (await persistentContext.cookies()).find(
      (cookie) => cookie.name === "gewebe_session",
    );
    expect(sessionCookie).toBeDefined();
    expect(sessionCookie?.httpOnly).toBe(true);
    expect(sessionCookie?.sameSite).toBe("Lax");
    expect(sessionCookie?.expires ?? -1).toBeGreaterThan(
      Math.floor(Date.now() / 1000) + 29 * 24 * 60 * 60,
    );
    proof.persistent_cookie = true;

    const secondPage = await persistentContext.newPage();
    await secondPage.goto(baseURL);
    await expect.poll(() => getAuthStatus(secondPage)).toMatchObject({
      authenticated: true,
      account_id: accountId,
    });
    proof.same_profile_second_window = true;

    await persistentContext.close();
    persistentContext = await chromium.launchPersistentContext(profileDir);
    const reopenedPage = persistentContext.pages()[0] ?? (await persistentContext.newPage());
    await reopenedPage.goto(baseURL);
    await expect.poll(() => getAuthStatus(reopenedPage)).toMatchObject({
      authenticated: true,
      account_id: accountId,
    });
    proof.browser_restart = true;

    isolatedBrowser = await chromium.launch();
    const isolatedContext = await isolatedBrowser.newContext();
    const isolatedPage = await isolatedContext.newPage();
    await isolatedPage.goto(baseURL);
    await expect.poll(() => getAuthStatus(isolatedPage)).toMatchObject({
      authenticated: false,
    });
    proof.isolated_profile = true;
    await isolatedContext.close();

    const reopenedSecondPage = await persistentContext.newPage();
    await reopenedSecondPage.goto(baseURL);
    const logoutStatus = await reopenedPage.evaluate(async () => {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
      return response.status;
    });
    expect(logoutStatus).toBe(200);
    await expect.poll(() => getAuthStatus(reopenedSecondPage)).toMatchObject({
      authenticated: false,
    });
    proof.logout_propagation = true;

    const proofDir = resolve(
      process.cwd(),
      "../../build/proofs/auth-session-browser",
    );
    await mkdir(proofDir, { recursive: true });
    await writeFile(
      join(proofDir, "proof-summary.json"),
      `${JSON.stringify(proof, null, 2)}\n`,
      "utf8",
    );
  } finally {
    await persistentContext.close().catch(() => undefined);
    await isolatedBrowser?.close().catch(() => undefined);
    await rm(profileDir, { recursive: true, force: true });
  }
});
