import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import jwt from "jsonwebtoken";
import { isSpcs, runQuery } from "./snowflake.js";

const SPCS_TOKEN_PATH = "/snowflake/session/token";

function resolveHome(filePath: string): string {
  if (filePath.startsWith("~/")) {
    return path.join(process.env.HOME ?? "", filePath.slice(2));
  }
  return filePath;
}

let cachedPrivateKey: string | null = null;
function getPrivateKey(): string {
  if (cachedPrivateKey) return cachedPrivateKey;
  const keyPath = resolveHome(process.env.SNOWFLAKE_PRIVATE_KEY_PATH ?? "");
  cachedPrivateKey = fs.readFileSync(keyPath, "utf-8");
  return cachedPrivateKey;
}

function getPublicKeyFingerprint(): string {
  const privateKey = getPrivateKey();
  const pubKeyObj = crypto.createPublicKey(privateKey);
  const pubKeyDer = pubKeyObj.export({ type: "spki", format: "der" });
  return crypto.createHash("sha256").update(pubKeyDer).digest("base64");
}

/** Local-dev key-pair JWT for the Cortex REST API. */
export function generateJwt(): string {
  const account = (process.env.SNOWFLAKE_ACCOUNT ?? "").toUpperCase();
  const user = (process.env.SNOWFLAKE_USER ?? "").toUpperCase();
  const fingerprint = getPublicKeyFingerprint();
  const qualifiedUser = `${account}.${user}`;
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: `${qualifiedUser}.SHA256:${fingerprint}`,
    sub: qualifiedUser,
    iat: now,
    exp: now + 3600,
  };
  return jwt.sign(payload, getPrivateKey(), { algorithm: "RS256" });
}

export interface AnalystMessage {
  role: string;
  content: Array<{ type: string; text?: string }>;
}

/**
 * Resolve the semantic view FQN to query.
 * - SPCS: env SEMANTIC_VIEW, else the consumer-set value in the app config table.
 * - Local: env SEMANTIC_VIEW, else the provider default.
 */
let cachedSemanticView: string | null = null;
async function getSemanticView(): Promise<string> {
  if (cachedSemanticView) return cachedSemanticView;
  if (process.env.SEMANTIC_VIEW) {
    cachedSemanticView = process.env.SEMANTIC_VIEW;
    return cachedSemanticView;
  }
  if (isSpcs()) {
    const rows = await runQuery(
      `SELECT value FROM config.settings WHERE key = 'semantic_view'`
    );
    const v = rows[0]?.value;
    if (typeof v === "string" && v.trim()) {
      cachedSemanticView = v.trim();
      return cachedSemanticView;
    }
    throw new Error(
      "Semantic view not configured. Run CALL config.set_semantic_view('<db>.<schema>.<view>')."
    );
  }
  cachedSemanticView = "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SUPPLY_CHAIN_360";
  return cachedSemanticView;
}

interface AuthCtx {
  url: string;
  token: string;
  tokenType: string;
}

function getAuthContext(): AuthCtx {
  if (isSpcs()) {
    const host = process.env.SNOWFLAKE_HOST!;
    return {
      url: `https://${host}/api/v2/cortex/analyst/message`,
      token: fs.readFileSync(SPCS_TOKEN_PATH, "ascii"),
      tokenType: "OAUTH",
    };
  }
  const account = process.env.SNOWFLAKE_ACCOUNT ?? "";
  return {
    url: `https://${account}.snowflakecomputing.com/api/v2/cortex/analyst/message`,
    token: generateJwt(),
    tokenType: "KEYPAIR_JWT",
  };
}

export async function callCortexAnalyst(
  messages: AnalystMessage[]
): Promise<unknown> {
  const { url, token, tokenType } = getAuthContext();
  const semanticView = await getSemanticView();

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      "X-Snowflake-Authorization-Token-Type": tokenType,
    },
    body: JSON.stringify({ messages, semantic_view: semanticView }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Cortex Analyst error ${response.status}: ${text}`);
  }
  return response.json();
}
