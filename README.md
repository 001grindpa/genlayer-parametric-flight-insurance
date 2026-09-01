# Flight Layer

Static frontend and Intelligent Contract for parametric flight-delay cover on
GenLayer StudioNet.

Live contract: [`0x725aCDe23e4d651146ED82C84508Bc87b8c3608A`](https://explorer-studio.genlayer.com/address/0x725aCDe23e4d651146ED82C84508Bc87b8c3608A)

A policyholder pays a premium for a **specific dated flight** and supplies two
trusted status URLs. Anyone can later call `resolve`. Validators fetch both
pages, bind the extract to that departure date, and agree on status and delay.
The verdict moves value in opposite directions:

- `APPROVED` pays coverage (equal to the premium) to the policyholder
- `REJECTED` keeps the premium in the contract

`ON_TIME` and `UNKNOWN` never pay.

## App

Static files only. Deploy the repo root on Vercel.

- `index.html`
- `static/app.js`
- `static/style.css`
- `src/ParametricFlightInsurance.py`

The browser app connects a wallet on StudioNet (`chainId` 61999), then calls:

- `create_policy(flight_number, departure_date, delay_threshold_minutes, status_url_a, status_url_b)` with premium as value
- `resolve(policy_id)`
- `get_policy`, `get_policy_status`, `get_policy_count`

## Contract API

Constructor takes no arguments. Policy IDs start at `"1"`.

### Create

```text
create_policy(
  flight_number="GL123",
  departure_date="2026-09-01",
  delay_threshold_minutes=120,
  status_url_a="https://www.flightaware.com/live/flight/GL123",
  status_url_b="https://www.flightradar24.com/data/flights/GL123"
)
```

Requirements:
- Flight number
- Departure date as `YYYY-MM-DD`
- Delay threshold > 0
- Two HTTPS URLs from **different** trusted hosts
- Non-zero premium

Trusted hosts: FlightAware, FlightStats, Flightradar24, Google, Bing, Kayak,
Expedia, AA, United, Delta, BA / British Airways, Lufthansa.

### Resolve

```text
resolve("1")
```

Both pages must match the stored departure date. Sources must agree on status
and delay within 15 minutes. Approved only if `CANCELLED`, or `DELAYED` and
delay ≥ threshold.

### Views

- `get_policy(policy_id)` — JSON including `departure_date`, `coverage`,
  `observed_date_match`, and `premium_disposition`
- `get_policy_status(policy_id)` — `ACTIVE` | `APPROVED` | `REJECTED`
- `get_policy_count()`
- `get_reserved_coverage()`
- `get_retained_premiums()`
