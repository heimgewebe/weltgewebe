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
        const decodeBase64Url = (value: string): Uint8Array => {
          const padded = value
            .replace(/-/g, "+")
            .replace(/_/g, "/")
            .padEnd(Math.ceil(value.length / 4) * 4, "=");
          const binary = atob(padded);
          return Uint8Array.from(binary, (char) => char.charCodeAt(0));
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

        const publicKey: PublicKeyCredentialCreationOptions = {
          ...creationOptions,
          challenge: decodeBase64Url(creationOptions.challenge),
          user: {
            ...creationOptions.user,
            id: decodeBase64Url(creationOptions.user.id),
          },
          excludeCredentials: (creationOptions.excludeCredentials ?? []).map(
            (descriptor) => ({
              ...descriptor,
              id: decodeBase64Url(descriptor.id),
            }),
          ),
        };

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
      expect(cookiesAfterVerify).toEqual(cookiesBeforeVerify);

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
        session_cookie_unchanged:
          JSON.stringify(cookiesBeforeVerify) ===
          JSON.stringify(cookiesAfterVerify),
        stored_credential_count: storedCredentialsBody.credential_ids.length,
        stored_credential_reflected:
          storedCredentialsBody.credential_ids.includes(credential.rawId),
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
      expect(proofSummary.virtual_authenticator_credentials).toBeGreaterThan(0);
    },
  );
});
