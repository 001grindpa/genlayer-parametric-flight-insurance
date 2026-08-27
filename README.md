# Parametric Flight Insurance

A GenLayer Intelligent Contract for flight-delay coverage. A policyholder pays a
premium when creating a policy. Anyone can later call `resolve`, which has the
validator network read the configured public status page and use an LLM to
extract a canonical delay decision. A claim is approved when the delay reaches
the threshold or the flight is cancelled.

The current payout is equal to the premium. This keeps the example fully
parameterized without introducing a second policy amount; change the payout
calculation in `resolve` before using it as a real insurance product.

## Contract API

The contract is in [ParametricFlightInsurance.py](ParametricFlightInsurance.py).

### Constructor

The constructor takes no arguments. The first policy receives ID `"1"`.

### Create a policy

Call the payable method with:

```text
create_policy(
	flight_number="GL123",
	delay_threshold_minutes=120,
	status_url="https://example.com/flight/GL123"
)
```

Attach the premium as the transaction value. The contract stores the sender,
flight number, threshold, URL, premium, and resolution fields on-chain. HTTP
and HTTPS URLs are accepted, but production deployments should additionally
restrict URLs to trusted flight-data providers.

### Resolve a policy

Call:

```text
resolve("1")
```

`resolve` fetches the page with `gl.nondet.web.get`, asks
`gl.nondet.exec_prompt` for only `delay_minutes` and `status`, and canonicalizes
the JSON before passing the operation to `gl.eq_principle.strict_eq`. The
consensus result is then stored as `APPROVED` or `REJECTED`. Approved policies
receive one payout equal to the attached premium and cannot be resolved again.

Use the read methods `get_policy("1")`, `get_policy_status("1")`, and
`get_policy_count()` to inspect state.

## Deploy With Studio

1. Open GenLayer Studio and create a new Intelligent Contract.
2. Paste the contents of `ParametricFlightInsurance.py` into the contract
	 editor. Studio detects the no-argument constructor.
3. Deploy the contract on the desired network.
4. From the deployed contract panel, call `create_policy`, supplying the three
	 arguments and a transaction value for the premium.
5. Call `resolve` with the returned policy ID, then inspect `get_policy`.

The contract must have enough balance to pay approved claims. Since the payout
is the premium, each policy's premium funds its own maximum payout, assuming no
other balance changes.

## Deploy With CLI

Install and configure the GenLayer CLI for your target network, then deploy:

```bash
genlayer deploy --contract ParametricFlightInsurance.py
```

There are no constructor arguments to provide for this contract. If your CLI
configuration requires an explicit argument flag, leave its argument list
empty according to that CLI version's help output.

Use the deployed address with the CLI's `call` and `write` commands. The exact
network and wallet flags depend on the CLI configuration; consult the official
[deployment guide](https://docs.genlayer.com/developers/intelligent-contracts/deploying)
for those flags and receipt handling. A payable write must include its value in
the CLI's transaction-value option.

## Design Notes

- Persistent fields use GenLayer storage types and an `@allow_storage` dataclass.
- Storage values needed by nondeterministic code are copied into local memory
	first; no storage object is accessed inside the equivalence-principle block.
- The LLM output is deliberately reduced to objective fields and serialized with
	sorted keys so strict equality is meaningful across validators.
- A failed or undetermined resolution does not commit the policy update. An
	external page should be stable, public, and contain the flight's current
	status in text accessible to the web reader.

See the official [Intelligent Contracts introduction](https://docs.genlayer.com/developers/intelligent-contracts/first-contract),
[storage guide](https://docs.genlayer.com/developers/intelligent-contracts/storage),
and [Equivalence Principle](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle)
documentation for SDK and network details.
