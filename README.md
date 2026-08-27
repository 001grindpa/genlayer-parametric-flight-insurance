# Flight Cover / GenLayer

Static frontend for the deployed Parametric Flight Insurance Intelligent
Contract. The app lives entirely in [index.html](index.html): vanilla browser
JavaScript, Tailwind via CDN, GenLayerJS via ESM CDN, and an injected EIP-1193
wallet such as MetaMask. There is no server, build step, or package manager
needed.

## Open Locally

Open `index.html` in a browser, or serve the folder with any static server:

```bash
python3 -m http.server 8080
```

Then visit `http://localhost:8080`. Connect MetaMask to Studionet when prompted.
The browser needs network access to the Tailwind, font, and GenLayerJS CDNs.

## Deploy To Vercel

Import this repository in Vercel, or drag the project folder into Vercel's
dashboard. Use the default settings: no framework preset, no build command,
and the project root as the output directory. Vercel will serve `index.html`
directly.

## Deployed Contract

- Network: GenLayer Studionet, chain ID `61999` (`0xf1ef`)
- RPC: `https://studio.genlayer.com/api`
- Contract: `0x1fc96d90F9A74f7c465e52DCc481E5080b012273`
- [Open contract in Studio Explorer](https://explorer-studio.genlayer.com/address/0x1fc96d90F9A74f7c465e52DCc481E5080b012273)
- [GenLayer Studio](https://studio.genlayer.com)
- [GenLayer documentation](https://docs.genlayer.com)

The frontend calls `create_policy(flight_number, delay_threshold_minutes,
status_url)` with the premium as native GEN value, `resolve(policy_id)`, and
the three view methods `get_policy`, `get_policy_status`, and
`get_policy_count`. Policy details are returned by the contract as a JSON
string and are pretty-printed in the lookup panel.

## Wallet Funding

You need MetaMask or another injected EIP-1193 wallet, connected to Studionet,
with GEN for transaction fees and premiums. Use the GEN faucet available from
the account selector in [GenLayer Studio](https://studio.genlayer.com). The
app will request the Studionet network automatically when connecting.

## Links

- [GenLayerJS browser integration](https://docs.genlayer.com/api-references/genlayer-js)
- [Value transfers and payable methods](https://docs.genlayer.com/developers/intelligent-contracts/features/value-transfers)
- [Contract source](ParametricFlightInsurance.py)
