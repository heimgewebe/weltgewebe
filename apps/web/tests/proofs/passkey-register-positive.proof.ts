import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

type BrowserFetchResult = {
  status: number;
  bodyText: string;
  json: unknown | null;
};

type RegisterOptionsResponse = {
  registration_id: string;
  options: {
    publicKey: {
      challenge: string;
      rp: { id: string; name: string };
      user: { id: string; name: string; displayName: string };
      pubKeyCredParams: Array<{ type: string; alg: number }>;
      timeout?: number;
      excludeCredentials?: Array<{ id: string; type: string }>;
      authenticatorSelection?: Record<string, unknown>;
      attestation?: string;
      extensions?: Record<string, unknown>;
    };
  };
};

type AuthOptionsResponse = {
  authentication_id: string;
  options: {
    publicKey: {
      challenge: string;
      timeout?: number;
      rpId?: string;
      allowCredentials?: Array<{ id: string; type: string }>;
      userVerification?: UserVerificationRequirement;
      extensions?: Record<string, unknown>;
    };
  };
};

test.describe("Passkey Register Positive Proof", () => {
  test(
    "proves positive passkey register verify with a virtual authenticator",
    { tag: "@proof" },
    async ({ browserName, page }, testInfo) => {
      test.skip(
        browserName !== "chromium",
        "virtual WebAuthn authenticator requires Chromium CDP",
      );

      const proofDir = path.resolve(
        process.cwd(),
        "../../build/proofs/auth-passkey-register",
      );
      fs.mkdirSync(proofDir, { recursive: true });

      const context = page.context();
      const proofEmail = "proof-passkey-user@example.com";
      const baseURL = testInfo.project.use.baseURL;
      if (typeof baseURL !== "string") {
        throw new Error("baseURL must be configured for the passkey proof");
      }

      const cdp = await context.newCDPSession(page);
      await cdp.send("WebAuthn.enable");
      const { authenticatorId } = await cdp.send(
        "WebAuthn.addVirtualAuthenticator",
        {
          options: {
            protocol: "ctap2",
            transport: "internal",
            hasResidentKey: true,
            hasUserVerification: true,
            isUserVerified: true,
            automaticPresenceSimulation: true,
          },
        },
      );

      const request = context.request;

      const postJsonInPage = async (
        url: string,
        payload?: unknown,
      ): Promise<BrowserFetchResult> =>
        page.evaluate(
          async ({ requestUrl, requestPayload }) => {
            const res = await fetch(requestUrl, {
              method: "POST",
              credentials: "include",
              headers:
                requestPayload === undefined
                  ? undefined
                  : {
                      "Content-Type": "application/json",
                    },
              body:
                requestPayload === undefined
                  ? undefined
                  : JSON.stringify(requestPayload),
            });
            const bodyText = await res.text();
            let json = null;
            if (bodyText.length > 0) {
              try {
                json = JSON.parse(bodyText);
              } catch {
                json = null;
              }
            }
            return {
              status: res.status,
              bodyText,
              json,
            };
          },
          {
            requestUrl: url,
            requestPayload: payload,
          },
        );

      const loginRes = await request.post(
        `${baseURL}/api/auth/testing/passkeys/bootstrap-session`,
      );
      expect(
        loginRes.status(),
        "bootstrap-session must create an authenticated session",
      ).toBe(200);
      const loginBody = (await loginRes.json()) as {
        account_id: string;
        device_id: string;
      };

      const cookiesBeforeVerify = await context.cookies(baseURL);
      const sessionCookieBefore = cookiesBeforeVerify.find(
        (cookie) => cookie.name === "gewebe_session",
      );
      expect(
        sessionCookieBefore,
        "proof setup must yield a session cookie",
      ).toBeTruthy();

      await page.goto(`${baseURL}/build?proof=passkey-register`);

      const grantRes = await postJsonInPage(
        `${baseURL}/api/auth/testing/passkeys/register/grant`,
      );
      expect(
        grantRes.status,
        `test-only grant hook must issue a registration grant; body=${grantRes.bodyText}`,
      ).toBe(200);
      const grantBody = grantRes.json as { registration_grant_id: string };
      expect(grantBody.registration_grant_id).toBeTruthy();

      const optionsRes = await postJsonInPage(
        `${baseURL}/api/auth/passkeys/register/options`,
        { registration_grant_id: grantBody.registration_grant_id },
      );
      expect(
        optionsRes.status,
        `register/options must succeed with a valid grant; body=${optionsRes.bodyText}`,
      ).toBe(200);
      const optionsBody = optionsRes.json as RegisterOptionsResponse;
      expect(optionsBody.registration_id).toBeTruthy();

      const credential = await page.evaluate(async (creationOptions) => {
        const decodeBase64Url = (value: string): ArrayBuffer => {
          const padded = value
            .replace(/-/g, "+")
            .replace(/_/g, "/")
            .padEnd(Math.ceil(value.length / 4) * 4, "=");
          const binary = atob(padded);
          const buffer = new ArrayBuffer(binary.length);
          const bytes = new Uint8Array(buffer);

          for (let i = 0; i < binary.length; i += 1) {
            bytes[i] = binary.charCodeAt(i);
          }

          return buffer;
        };

        const encodeBase64Url = (value: ArrayBuffer): string => {
          const bytes = new Uint8Array(value);
          let binary = "";
          for (const byte of bytes) {
            binary += String.fromCharCode(byte);
          }
          return btoa(binary)
            .replace(/\+/g, "-")
            .replace(/\//g, "_")
            .replace(/=+$/g, "");
        };

        const publicKey = {
          ...creationOptions,
          challenge: decodeBase64Url(creationOptions.challenge),
          user: {
            ...creationOptions.user,
            id: decodeBase64Url(creationOptions.user.id),
          },
          excludeCredentials: (creationOptions.excludeCredentials ?? []).map(
            (descriptor) => ({
              id: decodeBase64Url(descriptor.id),
              type: "public-key" as const,
            }),
          ),
        } as PublicKeyCredentialCreationOptions;

        const created = await navigator.credentials.create({ publicKey });
        if (!(created instanceof PublicKeyCredential)) {
          throw new Error(
            "navigator.credentials.create did not return a PublicKeyCredential",
          );
        }
        const response = created.response as AuthenticatorAttestationResponse;

        return {
          id: created.id,
          rawId: encodeBase64Url(created.rawId),
          response: {
            attestationObject: encodeBase64Url(response.attestationObject),
            clientDataJSON: encodeBase64Url(response.clientDataJSON),
            transports:
              typeof response.getTransports === "function"
                ? response.getTransports()
                : undefined,
          },
          type: created.type,
          clientExtensionResults: created.getClientExtensionResults(),
          authenticatorAttachment: created.authenticatorAttachment,
        };
      }, optionsBody.options.publicKey);

      const verifyResponsePromise = page.waitForResponse(
        (response) =>
          response.url() === `${baseURL}/api/auth/passkeys/register/verify` &&
          response.request().method() === "POST",
      );
      const verifyRes = await postJsonInPage(
        `${baseURL}/api/auth/passkeys/register/verify`,
        {
          registration_id: optionsBody.registration_id,
          credential,
        },
      );
      const verifyNetworkResponse = await verifyResponsePromise;
      expect(
        verifyRes.status,
        `register/verify must succeed with a real WebAuthn credential; body=${verifyRes.bodyText}`,
      ).toBe(200);
      expect(
        verifyNetworkResponse.headers()["set-cookie"],
        "register/verify must not emit Set-Cookie",
      ).toBeUndefined();
      expect(verifyRes.json).toEqual({ ok: true });

      const cookiesAfterVerify = await context.cookies(baseURL);
      const sessionCookieAfter = cookiesAfterVerify.find(
        (cookie) => cookie.name === "gewebe_session",
      );
      const sessionCookieUnchanged =
        sessionCookieAfter?.value === sessionCookieBefore?.value;
      expect(
        sessionCookieUnchanged,
        "register/verify must not rotate the session cookie",
      ).toBe(true);

      const storedCredentialsRes = await request.get(
        `${baseURL}/api/auth/testing/passkeys`,
      );
      expect(
        storedCredentialsRes.status(),
        "stored passkeys must be inspectable via the test-only hook",
      ).toBe(200);
      const storedCredentialsBody = (await storedCredentialsRes.json()) as {
        account_id: string;
        credential_ids: string[];
      };
      expect(
        storedCredentialsBody.credential_ids.length,
        "register/verify must insert a credential into PasskeyStore",
      ).toBeGreaterThan(0);
      expect(
        storedCredentialsBody.credential_ids.includes(credential.rawId),
        "stored credential ids must include the newly registered credential",
      ).toBe(true);

      await context.clearCookies();
      await page.goto(`${baseURL}/build?proof=passkey-auth`);

      const authOptionsResponsePromise = page.waitForResponse(
        (response) =>
          response.url() === `${baseURL}/api/auth/passkeys/auth/options` &&
          response.request().method() === "POST",
      );
      const authOptionsRes = await postJsonInPage(
        `${baseURL}/api/auth/passkeys/auth/options`,
        { email: proofEmail },
      );
      const authOptionsNetworkResponse = await authOptionsResponsePromise;
      expect(
        authOptionsRes.status,
        `auth/options must succeed after passkey registration; body=${authOptionsRes.bodyText}`,
      ).toBe(200);
      expect(
        authOptionsNetworkResponse.headers()["set-cookie"],
        "auth/options must not emit Set-Cookie",
      ).toBeUndefined();
      const authOptionsBody = authOptionsRes.json as AuthOptionsResponse;
      expect(authOptionsBody.authentication_id).toBeTruthy();
      expect(
        authOptionsBody.options.publicKey.allowCredentials?.length,
        "auth/options must expose an allowCredentials entry from the runtime store",
      ).toBeGreaterThan(0);

      const assertion = await page.evaluate(async (requestOptions) => {
        const decodeBase64Url = (value: string): ArrayBuffer => {
          const padded = value
            .replace(/-/g, "+")
            .replace(/_/g, "/")
            .padEnd(Math.ceil(value.length / 4) * 4, "=");
          const binary = atob(padded);
          const buffer = new ArrayBuffer(binary.length);
          const bytes = new Uint8Array(buffer);

          for (let i = 0; i < binary.length; i += 1) {
            bytes[i] = binary.charCodeAt(i);
          }

          return buffer;
        };

        const encodeBase64Url = (value: ArrayBuffer): string => {
          const bytes = new Uint8Array(value);
          let binary = "";
          for (const byte of bytes) {
            binary += String.fromCharCode(byte);
          }
          return btoa(binary)
            .replace(/\+/g, "-")
            .replace(/\//g, "_")
            .replace(/=+$/g, "");
        };

        const publicKey = {
          ...requestOptions,
          challenge: decodeBase64Url(requestOptions.challenge),
          allowCredentials: (requestOptions.allowCredentials ?? []).map(
            (descriptor) => ({
              id: decodeBase64Url(descriptor.id),
              type: "public-key" as const,
            }),
          ),
        } as PublicKeyCredentialRequestOptions;

        const credential = await navigator.credentials.get({ publicKey });
        if (!(credential instanceof PublicKeyCredential)) {
          throw new Error(
            "navigator.credentials.get did not return a PublicKeyCredential",
          );
        }
        const response = credential.response as AuthenticatorAssertionResponse;

        return {
          id: credential.id,
          rawId: encodeBase64Url(credential.rawId),
          response: {
            authenticatorData: encodeBase64Url(response.authenticatorData),
            clientDataJSON: encodeBase64Url(response.clientDataJSON),
            signature: encodeBase64Url(response.signature),
            userHandle:
              response.userHandle === null
                ? null
                : encodeBase64Url(response.userHandle),
          },
          type: credential.type,
          clientExtensionResults: credential.getClientExtensionResults(),
          authenticatorAttachment: credential.authenticatorAttachment,
        };
      }, authOptionsBody.options.publicKey);

      const authVerifyResponsePromise = page.waitForResponse(
        (response) =>
          response.url() === `${baseURL}/api/auth/passkeys/auth/verify` &&
          response.request().method() === "POST",
      );
      const authVerifyRes = await postJsonInPage(
        `${baseURL}/api/auth/passkeys/auth/verify`,
        {
          authentication_id: authOptionsBody.authentication_id,
          credential: assertion,
        },
      );
      const authVerifyNetworkResponse = await authVerifyResponsePromise;
      expect(
        authVerifyRes.status,
        `auth/verify must succeed with a real WebAuthn assertion; body=${authVerifyRes.bodyText}`,
      ).toBe(200);
      expect(authVerifyRes.json).toEqual({
        ok: true,
        account_id: loginBody.account_id,
      });
      expect(
        authVerifyNetworkResponse.headers()["set-cookie"],
        "auth/verify must mint a session cookie only after credential verification",
      ).toBeTruthy();
      const cookiesAfterAuthVerify = await context.cookies(baseURL);
      const loginSessionCookie = cookiesAfterAuthVerify.find(
        (cookie) => cookie.name === "gewebe_session",
      );
      expect(
        loginSessionCookie,
        "auth/verify must install a session cookie",
      ).toBeTruthy();

      const virtualCredentials = (await cdp.send("WebAuthn.getCredentials", {
        authenticatorId,
      })) as {
        credentials: Array<{
          credentialId: string;
          isResidentCredential: boolean;
        }>;
      };

      const proofSummary = {
        proof: "passkey-register-positive",
        account_id: loginBody.account_id,
        register_options_status: optionsRes.status,
        register_verify_status: verifyRes.status,
        register_verify_set_cookie:
          verifyNetworkResponse.headers()["set-cookie"] ?? null,
        session_cookie_unchanged: sessionCookieUnchanged,
        stored_credential_count: storedCredentialsBody.credential_ids.length,
        stored_credential_reflected:
          storedCredentialsBody.credential_ids.includes(credential.rawId),
        auth_options_status: authOptionsRes.status,
        auth_options_set_cookie:
          authOptionsNetworkResponse.headers()["set-cookie"] ?? null,
        auth_options_allow_credentials:
          authOptionsBody.options.publicKey.allowCredentials?.length ?? 0,
        auth_verify_status: authVerifyRes.status,
        auth_verify_set_cookie:
          authVerifyNetworkResponse.headers()["set-cookie"] ?? null,
        auth_verify_session_cookie_present: Boolean(loginSessionCookie),
        virtual_authenticator_credentials:
          virtualCredentials.credentials.length,
      };

      console.log(
        "PASSKEY_REGISTER_PROOF_SUMMARY:",
        JSON.stringify(proofSummary, null, 2),
      );
      fs.writeFileSync(
        testInfo.outputPath("proof-summary.json"),
        JSON.stringify(proofSummary, null, 2),
      );
      fs.writeFileSync(
        path.join(proofDir, "proof-summary.json"),
        JSON.stringify(proofSummary, null, 2),
      );

      expect(proofSummary.register_options_status).toBe(200);
      expect(proofSummary.register_verify_status).toBe(200);
      expect(proofSummary.register_verify_set_cookie).toBeNull();
      expect(proofSummary.session_cookie_unchanged).toBe(true);
      expect(proofSummary.stored_credential_reflected).toBe(true);
      expect(proofSummary.auth_options_status).toBe(200);
      expect(proofSummary.auth_options_set_cookie).toBeNull();
      expect(proofSummary.auth_options_allow_credentials).toBeGreaterThan(0);
      expect(proofSummary.auth_verify_status).toBe(200);
      expect(proofSummary.auth_verify_set_cookie).toBeTruthy();
      expect(proofSummary.auth_verify_session_cookie_present).toBe(true);
      expect(proofSummary.virtual_authenticator_credentials).toBeGreaterThan(0);
    },
  );
});
