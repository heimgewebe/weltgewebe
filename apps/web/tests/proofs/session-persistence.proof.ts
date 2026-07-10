import { chromium, expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const COOKIE_EXPIRY_SAFETY_SECONDS = 5 * 60;

type SessionStatus = {
  authenticated: boolean;
  expires_at?: string;
  device_id?: string;
};

type BootstrapStatus = {
  account_id: string;
  device_id: string;
};

type BrowserFetchResult<T> = {
  status: number;
  bodyText: string;
  json: T | null;
};

async function fetchInPage<T>(
  page: Page,
  url: string,
  method: "GET" | "POST" = "GET",
): Promise<BrowserFetchResult<T>> {
  return page.evaluate(
    async ({ requestUrl, requestMethod }) => {
      const response = await fetch(requestUrl, {
        method: requestMethod,
        credentials: "include",
      });
      const bodyText = await response.text();
      let json = null;
      if (bodyText.length > 0) {
        try {
          json = JSON.parse(bodyText);
        } catch {
          json = null;
        }
      }
      return { status: response.status, bodyText, json };
    },
    { requestUrl: url, requestMethod: method },
  );
}

async function openApiPage(page: Page, apiOrigin: string): Promise<void> {
  const response = await page.goto(`${apiOrigin}/health/ready`);
  expect(response?.status(), "API readiness page must load").toBe(200);
}

async function bootstrapSession(
  page: Page,
  apiOrigin: string,
): Promise<BootstrapStatus> {
  const bootstrap = await fetchInPage<BootstrapStatus>(
    page,
    `${apiOrigin}/auth/testing/passkeys/bootstrap-session`,
    "POST",
  );
  expect(
    bootstrap.status,
    `bootstrap session failed: ${bootstrap.bodyText}`,
  ).toBe(200);
  expect(bootstrap.json?.device_id).toBeTruthy();
  return bootstrap.json as BootstrapStatus;
}

async function readSession(
  page: Page,
  apiOrigin: string,
): Promise<SessionStatus> {
  const result = await fetchInPage<SessionStatus>(
    page,
    `${apiOrigin}/auth/session`,
  );
  expect(result.status, `session status failed: ${result.bodyText}`).toBe(200);
  expect(result.json).not.toBeNull();
  return result.json as SessionStatus;
}

test.describe("Persistent Browser Session Proof", () => {
  test(
    "proves shared-profile persistence, isolated sessions, restart, and server-side logout",
    { tag: "@proof" },
    async ({ browserName }, testInfo) => {
      expect(browserName, "proof must execute in Chromium").toBe("chromium");

      const apiOrigin = testInfo.project.use.baseURL;
      if (typeof apiOrigin !== "string") {
        throw new Error("baseURL must be configured for the session proof");
      }

      const proofDir = path.resolve(
        process.cwd(),
        "../../build/proofs/auth-session-persistence",
      );
      fs.mkdirSync(proofDir, { recursive: true });

      const primaryProfile = testInfo.outputPath("primary-profile");
      const separateProfile = testInfo.outputPath("separate-profile");

      let primary = await chromium.launchPersistentContext(primaryProfile, {
        headless: true,
      });
      const loginPage = primary.pages()[0] ?? (await primary.newPage());
      await openApiPage(loginPage, apiOrigin);

      const bootstrap = await bootstrapSession(loginPage, apiOrigin);
      const primaryStatus = await readSession(loginPage, apiOrigin);
      expect(primaryStatus.authenticated).toBe(true);
      expect(primaryStatus.device_id).toBe(bootstrap.device_id);
      expect(primaryStatus.expires_at).toBeTruthy();

      const sessionCookie = (await primary.cookies(apiOrigin)).find(
        (cookie) => cookie.name === "gewebe_session",
      );
      expect(sessionCookie, "login must set the session cookie").toBeTruthy();
      expect(sessionCookie?.httpOnly).toBe(true);
      expect(sessionCookie?.sameSite).toBe("Lax");
      expect(sessionCookie?.path).toBe("/");
      expect(sessionCookie?.secure).toBe(false);
      const serverExpiry =
        Date.parse(primaryStatus.expires_at as string) / 1000;
      expect(sessionCookie?.expires).toBeLessThanOrEqual(
        serverExpiry - COOKIE_EXPIRY_SAFETY_SECONDS,
      );
      expect(sessionCookie?.expires).toBeGreaterThanOrEqual(
        serverExpiry - COOKIE_EXPIRY_SAFETY_SECONDS - 1,
      );
      expect(
        sessionCookie?.expires ?? 0,
        "cookie must survive a normal browser restart",
      ).toBeGreaterThan(Date.now() / 1000 + 29 * 24 * 60 * 60);

      const secondPage = await primary.newPage();
      await openApiPage(secondPage, apiOrigin);
      const secondPageStatus = await readSession(secondPage, apiOrigin);
      expect(secondPageStatus.authenticated).toBe(true);
      expect(secondPageStatus.device_id).toBe(primaryStatus.device_id);

      const separate = await chromium.launchPersistentContext(separateProfile, {
        headless: true,
      });
      const separatePage = separate.pages()[0] ?? (await separate.newPage());
      await openApiPage(separatePage, apiOrigin);
      const separateBootstrap = await bootstrapSession(separatePage, apiOrigin);
      const separateStatus = await readSession(separatePage, apiOrigin);
      const separateCookie = (await separate.cookies(apiOrigin)).find(
        (cookie) => cookie.name === "gewebe_session",
      );
      expect(separateStatus.authenticated).toBe(true);
      expect(separateStatus.device_id).toBe(separateBootstrap.device_id);
      expect(separateStatus.device_id).not.toBe(primaryStatus.device_id);
      expect(separateCookie?.value).toBeTruthy();
      expect(separateCookie?.value).not.toBe(sessionCookie?.value);

      await primary.close();
      primary = await chromium.launchPersistentContext(primaryProfile, {
        headless: true,
      });
      const reopenedPage = primary.pages()[0] ?? (await primary.newPage());
      await openApiPage(reopenedPage, apiOrigin);
      const reopenedStatus = await readSession(reopenedPage, apiOrigin);
      expect(reopenedStatus.authenticated).toBe(true);
      expect(reopenedStatus.device_id).toBe(primaryStatus.device_id);

      // A second context in the same Chromium process models a private window:
      // it shares the browser process but not the persistent profile cookies.
      const persistentBrowser = primary.browser();
      expect(
        persistentBrowser,
        "persistent context must expose its browser",
      ).toBeTruthy();
      const privateContext = await persistentBrowser!.newContext();
      const privatePage = await privateContext.newPage();
      await openApiPage(privatePage, apiOrigin);
      expect((await readSession(privatePage, apiOrigin)).authenticated).toBe(
        false,
      );
      const privateBootstrap = await bootstrapSession(privatePage, apiOrigin);
      const privateStatus = await readSession(privatePage, apiOrigin);
      const privateCookie = (await privateContext.cookies(apiOrigin)).find(
        (cookie) => cookie.name === "gewebe_session",
      );
      expect(privateStatus.authenticated).toBe(true);
      expect(privateStatus.device_id).toBe(privateBootstrap.device_id);
      expect(privateStatus.device_id).not.toBe(primaryStatus.device_id);
      expect(privateStatus.device_id).not.toBe(separateStatus.device_id);
      expect(privateCookie?.value).toBeTruthy();
      expect(privateCookie?.value).not.toBe(sessionCookie?.value);
      expect(privateCookie?.value).not.toBe(separateCookie?.value);

      const observerPage = await primary.newPage();
      await openApiPage(observerPage, apiOrigin);
      expect((await readSession(observerPage, apiOrigin)).authenticated).toBe(
        true,
      );

      const logoutPage = await primary.newPage();
      await openApiPage(logoutPage, apiOrigin);
      const logout = await fetchInPage<unknown>(
        logoutPage,
        `${apiOrigin}/auth/logout`,
        "POST",
      );
      expect(logout.status, `logout failed: ${logout.bodyText}`).toBe(200);

      const observerAfterLogout = await readSession(observerPage, apiOrigin);
      expect(observerAfterLogout.authenticated).toBe(false);
      expect(
        (await primary.cookies(apiOrigin)).some(
          (cookie) => cookie.name === "gewebe_session",
        ),
      ).toBe(false);

      // Re-inject the pre-logout cookie into a fresh client. The request must
      // remain unauthenticated and the middleware must remove that stale cookie.
      // This assertion fails if logout only clears the browser cookie but leaves
      // the server-side session alive.
      const staleBrowser = await chromium.launch({ headless: true });
      const staleContext = await staleBrowser.newContext();
      await staleContext.addCookies([sessionCookie!]);
      expect(
        (await staleContext.cookies(apiOrigin)).some(
          (cookie) => cookie.name === "gewebe_session",
        ),
      ).toBe(true);
      const stalePage = await staleContext.newPage();
      await openApiPage(stalePage, apiOrigin);
      const staleStatus = await readSession(stalePage, apiOrigin);
      expect(staleStatus.authenticated).toBe(false);
      expect(
        (await staleContext.cookies(apiOrigin)).some(
          (cookie) => cookie.name === "gewebe_session",
        ),
      ).toBe(false);
      await staleBrowser.close();

      // Logging out the primary profile must not invalidate the independent
      // sessions created by the separate profile and private context.
      const separateAfterLogout = await readSession(separatePage, apiOrigin);
      const privateAfterLogout = await readSession(privatePage, apiOrigin);
      expect(separateAfterLogout.authenticated).toBe(true);
      expect(privateAfterLogout.authenticated).toBe(true);

      await privateContext.close();
      await primary.close();
      await separate.close();

      const summary = {
        proof: "auth-session-persistence",
        account_id: bootstrap.account_id,
        device_id: primaryStatus.device_id,
        persistent_cookie: {
          http_only: sessionCookie?.httpOnly,
          same_site: sessionCookie?.sameSite,
          path: sessionCookie?.path,
          secure_in_local_http_proof: sessionCookie?.secure,
          expires_unix: sessionCookie?.expires,
          server_expires_unix: serverExpiry,
          safety_seconds: COOKIE_EXPIRY_SAFETY_SECONDS,
        },
        same_profile_second_page_authenticated: secondPageStatus.authenticated,
        persisted_profile_reopen_authenticated: reopenedStatus.authenticated,
        separate_profile_has_independent_session:
          separateStatus.authenticated &&
          separateStatus.device_id !== primaryStatus.device_id,
        private_context_has_independent_session:
          privateStatus.authenticated &&
          privateStatus.device_id !== primaryStatus.device_id,
        logout_propagated_to_existing_page:
          observerAfterLogout.authenticated === false,
        old_cookie_rejected_after_logout: staleStatus.authenticated === false,
        independent_sessions_survived_primary_logout:
          separateAfterLogout.authenticated && privateAfterLogout.authenticated,
      };
      fs.writeFileSync(
        path.join(proofDir, "proof-summary.json"),
        `${JSON.stringify(summary, null, 2)}\n`,
      );
    },
  );
});
