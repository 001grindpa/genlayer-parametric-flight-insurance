# Parametric Flight Insurance

A GenLayer Intelligent Contract for parametric flight delay coverage. A
policyholder pays a premium when creating a policy. Anyone can later call
`resolve`, which has the validator network independently fetch flight status
from two trusted sources, corroborate the findings through consensus, and
determine eligibility. A claim is approved when the flight is cancelled, or
when status is `DELAYED` and the observed delay meets the threshold.
`ON_TIME` and `UNKNOWN` never qualify through the delay field.

The premium is always returned to the policyholder—either as a payout (if
eligible) or as a refund (if ineligible). The contract does not retain fees.

## Contract API

The contract is in [ParametricFlightInsurance.py](ParametricFlightInsurance.py).

### Constructor

The constructor takes no arguments. Policy IDs begin at `"1"` and increment.

### Create a policy

Call the payable method with:

```text
create_policy(
	flight_number="GL123",
	delay_threshold_minutes=120,
	status_url_a="https://www.flightaware.com/live/flight/GL123",
	status_url_b="https://www.flightradar24.com/data/flights/GL123"
)
```

Attach the premium as the transaction value. The contract requires:
- Flight number (non-empty string)
- Delay threshold in minutes (must be > 0)
- Two HTTPS status URLs from different trusted hosts

Status URLs must come from the trusted list of hosts, with or without `www`:
- flightaware.com, flightstats.com, flightradar24.com
- google.com, bing.com, kayak.com, expedia.com
- aa.com, united.com, delta.com, ba.com, britishairways.com, lufthansa.com

A non-zero premium is required. The method returns the policy ID as a string.
The premium is locked as `RESERVED` until `resolve`.

### Resolve a policy

Call:

```text
resolve("1")
```

`resolve` independently fetches and parses both status URLs using
`gl.nondet.web.get` and `gl.nondet.exec_prompt`. The two sources must agree on
flight status and delay (within 15 minutes). The consensus result is validated
through `gl.eq_principle.strict_eq`.

A policy is approved if:
- Flight status is `CANCELLED`, OR
- Flight status is `DELAYED` AND observed delay ≥ threshold

`ON_TIME` and `UNKNOWN` cannot pay, even if the extracted delay is large.

In all cases (approved or rejected), the full premium is transferred back to the
policyholder. Approved policies set `premium_disposition` to
`PAID_TO_POLICYHOLDER`. Rejected policies set it to
`REFUNDED_TO_POLICYHOLDER`. Policies can only be resolved once.

### View methods

- `get_policy(policy_id)` — Returns the full policy state as JSON, including
  `payout_eligible` and `premium_disposition`
- `get_policy_status(policy_id)` — Returns the policy status (`ACTIVE`,
  `APPROVED`, or `REJECTED`)
- `get_policy_count()` — Returns the total number of policies created
- `get_reserved_premiums()` — Returns the sum of premiums awaiting resolution

## Deploy With Studio

1. Open GenLayer Studio and create a new Intelligent Contract.
2. Paste the contents of `ParametricFlightInsurance.py` into the contract
   editor. Studio detects the no-argument constructor.
3. Deploy the contract on the desired network.
4. From the deployed contract panel, call `create_policy`, supplying:
   - Flight number (e.g., "GL123")
   - Delay threshold in minutes (e.g., 120)
   - Two HTTPS URLs from different trusted hosts
   - A transaction value for the premium
5. Wait for finalization. The returned policy ID can be used to resolve later.
6. Call `resolve` with the policy ID once the flight has completed.
7. Use `get_policy` to inspect the final policy state, including `payout_eligible`
   and `premium_disposition`.

## Deploy With CLI

Install and configure the GenLayer CLI for your target network, then deploy:

```bash
genlayer deploy --contract ParametricFlightInsurance.py
```

There are no constructor arguments. Use the deployed address with the CLI's
`call` and `write` commands. Consult the official
[deployment guide](https://docs.genlayer.com/developers/intelligent-contracts/deploying)
for network and wallet flags.

To create a policy via CLI:

```bash
genlayer write <contract_address> create_policy \
  --arg flight_number "GL123" \
  --arg delay_threshold_minutes 120 \
  --arg status_url_a "https://www.flightaware.com/live/flight/GL123" \
  --arg status_url_b "https://www.flightradar24.com/data/flights/GL123" \
  --value "1000000000000000000"  # 1 GEN in wei
```

To resolve a policy:

```bash
genlayer write <contract_address> resolve --arg policy_id "1"
```

## Design Notes

- The contract requires two independent status URLs to reduce oracle manipulation
  risk. Both sources must be from the trusted host list and different hosts.
- Policies are immutable except through the `resolve` method, which transitions
  them from `ACTIVE` to either `APPROVED` or `REJECTED`.
- Delay corroboration uses a 15-minute tolerance; sources must agree within this
  window. If they disagree beyond this, resolution fails.
- Premiums are held in `reserved_premiums` during the `ACTIVE` state and
  transferred back to the policyholder (not kept by the contract) on resolution,
  regardless of eligibility.
- Eligibility is status-gated so a large delay cannot pay on `ON_TIME` or
  `UNKNOWN`.
- The LLM prompt is carefully worded to extract only objective flight facts:
  delay in minutes and flight status (ON_TIME, DELAYED, CANCELLED, or UNKNOWN).
- Consensus is established through `gl.eq_principle.strict_eq`, ensuring
  deterministic agreement across validators.

See the official [Intelligent Contracts introduction](https://docs.genlayer.com/developers/intelligent-contracts/first-contract),
[storage guide](https://docs.genlayer.com/developers/intelligent-contracts/storage),
and [Equivalence Principle](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle)
documentation for SDK and network details.
