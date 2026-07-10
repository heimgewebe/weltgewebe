import { chromium, expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

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

async function readSession(page: Page, apiOrigin: string): Promise<SessionStatus> {
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
    "proves shared-profile persistence, isolation, restart, and logout propagation",
    { tag: "@proof" },
    async ({}, testInfo) => {
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

      const bootstrap = await fetchInPage<BootstrapStatus>(
        loginPage,
        `${apiOrigin}/auth/testing/passkeys/bootstrap-session`,
        "POST",
      );
      expect(
        bootstrap.status,
        `bootstrap session failed: ${bootstrap.bodyText}`,
      ).toBe(200);
      expect(bootstrap.json?.device_id).toBeTruthy();

      const primaryStatus = await readSession(loginPage, apiOrigin);
      expect(primaryStatus.authenticated).toBe(true);
      expect(primaryStatus.device_id).toBe(bootstrap.json?.device_id);

      const sessionCookie = (await primary.cookies(apiOrigin)).find(
        (cookie) => cookie.name === "gewebe_session",
      );
      expect(sessionCookie, "login must set the session cookie").toBeTruthy();
      expect(sessionCookie?.httpOnly).toBe(true);
      expect(sessionCookie?.sameSite).toBe("Lax");
      expect(sessionCookie?.path).toBe("/");
      expect(sessionCookie?.secure).toBe(false);
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
      const separateStatus = await readSession(separatePage, apiOrigin);
      expect(separateStatus.authenticated).toBe(false);
      await separate.close();

      const privateBrowser = await chromium.launch({ headless: true });
      const privateContext = await privateBrowser.newContext();
      const privatePage = await privateContext.newPage();
      await openApiPage(privatePage, apiOrigin);
      const privateStatus = await readSession(privatePage, apiOrigin);
      expect(privateStatus.authenticated).toBe(false);
      await privateBrowser.close();

      await primary.close();
      primary = await chromium.launchPersistentContext(primaryProfile, {
        headless: true,
      });
      const reopenedPage = primary.pages()[0] ?? (await primary.newPage());
      await openApiPage(reopenedPage, apiOrigin);
      const reopenedStatus = await readSession(reopenedPage, apiOrigin);
      expect(reopenedStatus.authenticated).toBe(true);
      expect(reopenedStatus.device_id).toBe(primaryStatus.device_id);

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

      await primary.close();

      const summary = {
        proof: "auth-session-persistence",
        account_id: bootstrap.json?.account_id,
        device_id: primaryStatus.device_id,
        persistent_cookie: {
          http_only: sessionCookie?.httpOnly,
          same_site: sessionCookie?.sameSite,
          path: sessionCookie?.path,
          secure_in_local_http_proof: sessionCookie?.secure,
          expires_unix: sessionCookie?.expires,
        },
        same_profile_second_page_authenticated: secondPageStatus.authenticated,
        persisted_profile_reopen_authenticated: reopenedStatus.authenticated,
        separate_profile_authenticated: separateStatus.authenticated,
        private_context_authenticated: privateStatus.authenticated,
        logout_propagated_to_existing_page:
          observerAfterLogout.authenticated === false,
      };
      fs.writeFileSync(
        path.join(proofDir, "proof-summary.json"),
        `${JSON.stringify(summary, null, 2)}\n`,
      );
    },
  );
});
