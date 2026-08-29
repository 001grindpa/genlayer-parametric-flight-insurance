import { createClient } from 'https://esm.sh/genlayer-js@0.18.0?bundle';

const CONTRACT_ADDRESS = '0x733A3ad2FA449250e4F193B12c92cddc1B9b35DE';
const RPC_URL = 'https://studio.genlayer.com/api';
const CHAIN_ID = 61999;
const CHAIN_HEX = '0xf1ef';
const EXPLORER_URL = `https://explorer-studio.genlayer.com/address/`;
const TRUSTED_HOSTS = [
  'flightaware.com', 'flightstats.com', 'flightradar24.com', 'google.com', 'bing.com',
  'kayak.com', 'expedia.com', 'aa.com', 'united.com', 'delta.com', 'ba.com',
  'britishairways.com', 'lufthansa.com'
];
const studionet = {
  id: CHAIN_ID,
  name: 'GenLayer Studionet',
  nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
  rpcUrls: { default: { http: [RPC_URL] } },
  blockExplorers: { default: { name: 'Studio Explorer', url: 'https://explorer-studio.genlayer.com' } },
  isStudio: true
};

const $ = (id) => document.getElementById(id);
const state = { account: null, readClient: createClient({ chain: studionet, endpoint: RPC_URL }), writeClient: null };

function setActivity(message, tone = 'normal') {
  $('activity-message').textContent = message;
  $('activity-message').className = `mt-2 text-sm ${tone === 'error' ? 'text-[var(--coral)]' : tone === 'success' ? 'text-[var(--lime)]' : 'text-white/55'}`;
}
function showToast(title, body = '', tone = 'normal') {
  const toast = $('toast');
  $('toast-title').textContent = title;
  $('toast-body').textContent = body;
  toast.style.borderColor = tone === 'error' ? 'rgba(255,131,109,.55)' : tone === 'success' ? 'rgba(215,243,107,.5)' : 'rgba(244,241,233,.15)';
  toast.classList.remove('opacity-0', 'translate-y-5');
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => toast.classList.add('opacity-0', 'translate-y-5'), 5000);
}
function setBusy(button, busy, label) {
  button.disabled = busy;
  button.querySelector('span')?.replaceChildren(document.createTextNode(busy ? label : button.dataset.label || label));
}
function explorerLink(path) { return `${EXPLORER_URL}${path}`; }
function displayContractLink() {
  $('tx-link').classList.remove('hidden');
  $('tx-hash').href = explorerLink(CONTRACT_ADDRESS);
  $('tx-hash').textContent = CONTRACT_ADDRESS;
}
function displayTx(hash) {
  $('tx-link').classList.remove('hidden');
  $('tx-hash').href = explorerLink(hash);
  $('tx-hash').textContent = hash;
}
function parseGen(value) {
  const normalized = value.trim();
  if (!/^\d+(\.\d{1,18})?$/.test(normalized) || Number(normalized) <= 0) throw new Error('Premium must be a positive GEN amount with up to 18 decimals.');
  const [whole, fraction = ''] = normalized.split('.');
  return BigInt(whole) * 1000000000000000000n + BigInt(fraction.padEnd(18, '0'));
}
function shortAddress(address) { return `${address.slice(0, 6)}...${address.slice(-4)}`; }
function extractHost(urlString) {
  try {
    const url = new URL(urlString);
    return url.hostname.replace(/^www\./, '').toLowerCase();
  } catch {
    return null;
  }
}
function isHttps(urlString) {
  try {
    return new URL(urlString).protocol === 'https:';
  } catch {
    return false;
  }
}
function isValidTrustedHost(host) {
  return TRUSTED_HOSTS.some(trusted => host === trusted || host === `www.${trusted}`);
}
function validateDualUrls(urlA, urlB) {
  if (!isHttps(urlA) || !isHttps(urlB)) {
    return { valid: false, error: 'Both URLs must use HTTPS.' };
  }
  const hostA = extractHost(urlA);
  const hostB = extractHost(urlB);
  if (!hostA || !hostB) {
    return { valid: false, error: 'Invalid URL format.' };
  }
  if (!isValidTrustedHost(hostA) || !isValidTrustedHost(hostB)) {
    return { valid: false, error: `URLs must be from trusted hosts: ${TRUSTED_HOSTS.join(', ')}` };
  }
  if (hostA === hostB) {
    return { valid: false, error: 'Source A and Source B must be from different hosts.' };
  }
  return { valid: true };
}
function normalizeResult(result) {
  if (typeof result === 'bigint') return result.toString();
  if (typeof result === 'string') return result;
  return String(result);
}
async function read(method, args = []) {
  return state.readClient.readContract({ address: CONTRACT_ADDRESS, functionName: method, args, stateStatus: 'accepted' });
}
async function ensureNetwork() {
  if (!window.ethereum) throw new Error('No injected wallet found. Install MetaMask or another EIP-1193 wallet.');
  const current = await window.ethereum.request({ method: 'eth_chainId' });
  if (current.toLowerCase() === CHAIN_HEX) return;
  try {
    await window.ethereum.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: CHAIN_HEX }] });
  } catch (error) {
    if (error.code !== 4902) throw error;
    await window.ethereum.request({ method: 'wallet_addEthereumChain', params: [{ chainId: CHAIN_HEX, chainName: 'GenLayer Studionet', nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 }, rpcUrls: [RPC_URL], blockExplorerUrls: ['https://explorer-studio.genlayer.com'] }] });
  }
}
async function connectWallet() {
  if (!window.ethereum) throw new Error('No injected wallet found. Install MetaMask or another EIP-1193 wallet.');
  await ensureNetwork();
  const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
  state.account = accounts[0];
  state.writeClient = createClient({ chain: studionet, account: state.account, provider: window.ethereum });
  $('connect-btn').textContent = shortAddress(state.account);
  $('connect-btn').classList.remove('bg-[var(--lime)]');
  $('connect-btn').classList.add('border', 'border-white/20');
  setActivity(`Wallet connected: ${shortAddress(state.account)}. Ready for a policy transaction.`);
  showToast('Wallet connected', `Using ${shortAddress(state.account)} on Studionet.`, 'success');
}
async function requireWallet() {
  if (!state.account) await connectWallet();
  await ensureNetwork();
  return state.writeClient;
}
async function waitForFinalized(client, hash) {
  const receipt = await client.waitForTransactionReceipt({ hash, status: 'FINALIZED' });
  if (receipt?.txExecutionResultName && receipt.txExecutionResultName !== 'FINISHED_WITH_RETURN') throw new Error(`Contract execution did not finish successfully: ${receipt.txExecutionResultName}`);
  return receipt;
}
async function refreshCount() {
  try { $('policy-count').textContent = normalizeResult(await read('get_policy_count')); } catch { $('policy-count').textContent = '—'; }
}
async function lookupPolicy(policyId) {
  if (!policyId.trim()) throw new Error('Enter a policy ID.');
  const [rawPolicy, status] = await Promise.all([read('get_policy', [policyId.trim()]), read('get_policy_status', [policyId.trim()])]);
  let pretty;
  try { pretty = JSON.stringify(JSON.parse(normalizeResult(rawPolicy)), null, 2); } catch { pretty = normalizeResult(rawPolicy); }
  $('lookup-result').classList.remove('hidden');
  $('lookup-status').textContent = normalizeResult(status);
  $('lookup-status').className = `rounded-full border px-3 py-1 text-xs font-semibold ${normalizeResult(status) === 'APPROVED' ? 'border-[var(--lime)]/40 text-[var(--lime)]' : normalizeResult(status) === 'REJECTED' ? 'border-[var(--coral)]/40 text-[var(--coral)]' : 'border-white/15 text-white/65'}`;
  $('policy-json').textContent = pretty;
}

$('connect-btn').addEventListener('click', async () => { try { await connectWallet(); } catch (error) { showToast('Wallet connection failed', error.message || String(error), 'error'); } });
$('create-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('create-btn');
  try {
    const client = await requireWallet();
    const flight = $('flight-number').value.trim();
    const threshold = Number($('delay-threshold').value);
    const urlA = $('status-url-a').value.trim();
    const urlB = $('status-url-b').value.trim();
    const value = parseGen($('premium').value);
    if (!flight || !Number.isInteger(threshold) || threshold < 1) throw new Error('Check the flight number and delay threshold.');
    const validation = validateDualUrls(urlA, urlB);
    if (!validation.valid) throw new Error(validation.error);
    const countBefore = BigInt(normalizeResult(await read('get_policy_count')));
    setBusy(button, true, 'Waiting for wallet...');
    setActivity('Confirm the premium transaction in your wallet.');
    const hash = await client.writeContract({ address: CONTRACT_ADDRESS, functionName: 'create_policy', args: [flight, threshold, urlA, urlB], value });
    displayTx(hash);
    setActivity('Policy transaction submitted. Waiting for Studionet finalization.');
    await waitForFinalized(state.readClient, hash);
    const countAfter = BigInt(normalizeResult(await read('get_policy_count')));
    const policyId = countAfter > countBefore ? countAfter.toString() : countBefore.toString();
    $('resolve-policy-id').value = policyId;
    $('lookup-policy-id').value = policyId;
    await lookupPolicy(policyId);
    await refreshCount();
    displayContractLink();
    setActivity(`Policy #${policyId} is live and funded.`, 'success');
    showToast(`Policy #${policyId} created`, 'Your premium is now held by the contract.', 'success');
    $('create-form').reset();
  } catch (error) { setActivity(error.message || String(error), 'error'); showToast('Create policy failed', error.message || String(error), 'error'); }
  finally { setBusy(button, false, 'Create policy'); }
});
$('resolve-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('resolve-btn');
  const policyId = $('resolve-policy-id').value.trim();
  try {
    const client = await requireWallet();
    if (!/^\d+$/.test(policyId)) throw new Error('Policy ID must be a number.');
    setBusy(button, true, 'Resolve');
    setActivity(`Submitting resolution for policy #${policyId}.`);
    const hash = await client.writeContract({ address: CONTRACT_ADDRESS, functionName: 'resolve', args: [policyId] });
    displayTx(hash);
    setActivity('Resolution submitted. Consensus finalization may take a few minutes.');
    await waitForFinalized(state.readClient, hash);
    await lookupPolicy(policyId);
    displayContractLink();
    setActivity(`Policy #${policyId} has been resolved.`, 'success');
    showToast('Resolution complete', `Policy #${policyId} has been updated on-chain.`, 'success');
  } catch (error) { setActivity(error.message || String(error), 'error'); showToast('Resolution failed', error.message || String(error), 'error'); }
  finally { setBusy(button, false, 'Resolve'); }
});
$('lookup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('lookup-btn');
  try { setBusy(button, true, 'Lookup'); await lookupPolicy($('lookup-policy-id').value); setActivity('Showing the latest accepted policy state.', 'success'); }
  catch (error) { setActivity(error.message || String(error), 'error'); showToast('Lookup failed', error.message || String(error), 'error'); }
  finally { setBusy(button, false, 'Lookup'); }
});
if (window.ethereum) {
  window.ethereum.on('accountsChanged', (accounts) => { if (!accounts.length) { state.account = null; $('connect-btn').textContent = 'Connect wallet'; setActivity('Wallet disconnected.'); } else { state.account = accounts[0]; $('connect-btn').textContent = shortAddress(state.account); } });
  window.ethereum.on('chainChanged', () => { setActivity('Network changed. Studionet is required for transactions.', 'error'); });
}
refreshCount();
