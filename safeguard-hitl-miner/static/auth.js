/**
 * Polkadot.js extension authentication module.
 *
 * Handles: extension detection, account listing, challenge-response signing,
 * and session token management.
 */

// Polkadot.js extension imports from CDN
import {
  web3Enable,
  web3Accounts,
  web3FromAddress,
} from "https://esm.sh/@polkadot/extension-dapp@0.52.3";
import { u8aToHex, stringToU8a } from "https://esm.sh/@polkadot/util@13.2.3";

const SESSION_KEY = "hitl_session_token";
const SESSION_ADDRESS_KEY = "hitl_session_address";

/**
 * Check if the polkadot.js extension is available.
 */
export function detectExtension() {
  return typeof window.injectedWeb3 !== "undefined" &&
    Object.keys(window.injectedWeb3).length > 0;
}

/**
 * Connect to the polkadot.js extension and list available accounts.
 * Returns an array of {address, meta: {name, source}} objects.
 */
export async function connectWallet() {
  const extensions = await web3Enable("safeguard-hitl");
  if (extensions.length === 0) {
    throw new Error(
      "No polkadot.js extension found. Install it from https://polkadot.js.org/extension/"
    );
  }

  const accounts = await web3Accounts();
  if (accounts.length === 0) {
    throw new Error(
      "No accounts found in the extension. Import your hotkey first."
    );
  }

  return accounts;
}

/**
 * Perform challenge-response authentication with the server.
 *
 * 1. Request a nonce from the server for the given address
 * 2. Sign the nonce with the polkadot.js extension
 * 3. Send the signature to the server for verification
 * 4. Store the session token on success
 *
 * @param {string} address - SS58 address of the account to authenticate
 * @returns {string} The session token
 */
export async function authenticate(address) {
  // Step 1: Get nonce from server
  const nonceResp = await fetch(`/auth/nonce/${address}`);
  if (!nonceResp.ok) {
    const err = await nonceResp.json().catch(() => ({}));
    throw new Error(err.detail || `Nonce request failed: ${nonceResp.status}`);
  }
  const { nonce, token: nonceToken } = await nonceResp.json();

  // Step 2: Sign the nonce with the extension
  const injector = await web3FromAddress(address);
  const nonceBytes = stringToU8a(nonce);
  const { signature } = await injector.signer.signRaw({
    address,
    data: u8aToHex(nonceBytes),
    type: "bytes",
  });

  // Step 3: Verify with server
  const verifyResp = await fetch("/auth/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      address,
      nonce,
      signature,
      token: nonceToken,
    }),
  });

  if (!verifyResp.ok) {
    const err = await verifyResp.json().catch(() => ({}));
    throw new Error(err.detail || `Verification failed: ${verifyResp.status}`);
  }

  const { session_token } = await verifyResp.json();

  // Step 4: Store session
  localStorage.setItem(SESSION_KEY, session_token);
  localStorage.setItem(SESSION_ADDRESS_KEY, address);

  return session_token;
}

/**
 * Get the stored session token, or null if not authenticated.
 */
export function getSessionToken() {
  return localStorage.getItem(SESSION_KEY);
}

/**
 * Get the stored session address, or null.
 */
export function getSessionAddress() {
  return localStorage.getItem(SESSION_ADDRESS_KEY);
}

/**
 * Clear the stored session.
 */
export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(SESSION_ADDRESS_KEY);
}
