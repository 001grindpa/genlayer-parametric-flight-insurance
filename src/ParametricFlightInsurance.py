# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from genlayer import *


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


ALLOWED_HOSTS = (
    "flightaware.com",
    "www.flightaware.com",
    "flightstats.com",
    "www.flightstats.com",
    "flightradar24.com",
    "www.flightradar24.com",
    "google.com",
    "www.google.com",
    "bing.com",
    "www.bing.com",
    "kayak.com",
    "www.kayak.com",
    "expedia.com",
    "www.expedia.com",
    "aa.com",
    "www.aa.com",
    "united.com",
    "www.united.com",
    "delta.com",
    "www.delta.com",
    "ba.com",
    "www.ba.com",
    "britishairways.com",
    "www.britishairways.com",
    "lufthansa.com",
    "www.lufthansa.com",
)

DATE_RE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


@allow_storage
@dataclass
class FlightPolicy:
    policyholder: Address
    flight_number: str
    departure_date: str
    delay_threshold_minutes: u32
    status_url_a: str
    status_url_b: str
    premium: u256
    coverage: u256
    reserved: u256
    status: str
    observed_delay_minutes: i32
    observed_status: str
    observed_date_match: bool
    payout_eligible: bool
    premium_disposition: str


class ParametricFlightInsurance(gl.Contract):
    policies: TreeMap[str, FlightPolicy]
    next_policy_id: u256
    reserved_coverage: u256
    retained_premiums: u256

    def __init__(self):
        self.next_policy_id = 1
        self.reserved_coverage = 0
        self.retained_premiums = 0

    def _host(self, url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    def _assert_trusted_url(self, url: str) -> None:
        if not url.startswith("https://"):
            raise gl.vm.UserError("status URL must use https")
        host = self._host(url)
        allowed = False
        for allowed_host in ALLOWED_HOSTS:
            if host == allowed_host or host.endswith("." + allowed_host):
                allowed = True
                break
        if not allowed:
            raise gl.vm.UserError("status URL host is not on the trusted list")

    def _assert_independent_pair(self, url_a: str, url_b: str) -> None:
        self._assert_trusted_url(url_a)
        self._assert_trusted_url(url_b)
        if url_a.strip() == url_b.strip():
            raise gl.vm.UserError("the two status URLs must be distinct")
        if self._host(url_a) == self._host(url_b):
            raise gl.vm.UserError("the two status URLs must come from different hosts")

    def _extract_from_url(
        self,
        status_url: str,
        flight_number: str,
        departure_date: str,
        threshold: u32,
    ) -> dict:
        page = gl.nondet.web.get(status_url)
        page_text = page.body.decode("utf-8")[:6000]
        prompt = f"""
You are extracting facts for one specific dated flight from a public status page.
Flight number: {flight_number}
Scheduled departure date (YYYY-MM-DD): {departure_date}
Delay threshold in minutes: {threshold}
Page URL: {status_url}
Page content:
{page_text}

Return JSON only, with exactly these fields:
{{
  "flight_number": "string or UNKNOWN",
  "departure_date": "YYYY-MM-DD or UNKNOWN",
  "date_match": true or false,
  "delay_minutes": integer,
  "status": "ON_TIME"|"DELAYED"|"CANCELLED"|"UNKNOWN"
}}
Rules:
- Bind the extract to this flight number AND this departure date.
- date_match is true only if the page is clearly about that calendar date.
- If the page is about a different day, set date_match false and status UNKNOWN.
- Use the reported departure delay in minutes.
- Use 0 when the page clearly says this dated flight is on time.
- Use -1 when no delay can be established.
- Use CANCELLED only when this dated flight is explicitly cancelled.
"""
        extracted = json.loads(gl.nondet.exec_prompt(prompt))
        status = str(extracted.get("status", "UNKNOWN")).upper()
        if status not in ("ON_TIME", "DELAYED", "CANCELLED", "UNKNOWN"):
            status = "UNKNOWN"
        delay_minutes = int(extracted.get("delay_minutes", -1))
        if delay_minutes < -1:
            delay_minutes = -1
        date_match = bool(extracted.get("date_match", False))
        return {
            "flight_number": str(extracted.get("flight_number", "UNKNOWN"))[:16],
            "departure_date": str(extracted.get("departure_date", "UNKNOWN"))[:10],
            "date_match": date_match,
            "delay_minutes": delay_minutes,
            "status": status,
        }

    @gl.public.write.payable
    def create_policy(
        self,
        flight_number: str,
        departure_date: str,
        delay_threshold_minutes: u32,
        status_url_a: str,
        status_url_b: str,
    ) -> str:
        if not flight_number.strip():
            raise gl.vm.UserError("flight number is required")
        date = departure_date.strip()
        if re.match(DATE_RE, date) is None:
            raise gl.vm.UserError("departure date must be YYYY-MM-DD")
        if delay_threshold_minutes == 0:
            raise gl.vm.UserError("delay threshold must be greater than zero")
        self._assert_independent_pair(status_url_a, status_url_b)

        premium = gl.message.value
        if premium == 0:
            raise gl.vm.UserError("a non-zero premium is required")

        coverage = premium
        policy_id = str(self.next_policy_id)
        self.policies[policy_id] = FlightPolicy(
            policyholder=gl.message.sender_address,
            flight_number=flight_number.strip().upper(),
            departure_date=date,
            delay_threshold_minutes=delay_threshold_minutes,
            status_url_a=status_url_a.strip(),
            status_url_b=status_url_b.strip(),
            premium=premium,
            coverage=coverage,
            reserved=coverage,
            status="ACTIVE",
            observed_delay_minutes=-1,
            observed_status="UNRESOLVED",
            observed_date_match=False,
            payout_eligible=False,
            premium_disposition="RESERVED",
        )
        self.reserved_coverage = self.reserved_coverage + coverage
        self.next_policy_id = self.next_policy_id + 1
        return policy_id

    @gl.public.write
    def resolve(self, policy_id: str) -> None:
        if policy_id not in self.policies:
            raise gl.vm.UserError("policy not found")
        policy = self.policies[policy_id]
        if policy.status != "ACTIVE":
            raise gl.vm.UserError("policy has already been resolved")
        if policy.reserved != policy.coverage:
            raise gl.vm.UserError("policy reserve is inconsistent")
        if self.balance < policy.reserved:
            raise gl.vm.UserError("contract is not solvent for this coverage")

        status_url_a = policy.status_url_a
        status_url_b = policy.status_url_b
        flight_number = policy.flight_number
        departure_date = policy.departure_date
        threshold = policy.delay_threshold_minutes
        policyholder = policy.policyholder
        coverage = policy.coverage

        def fetch_and_corroborate() -> str:
            a = self._extract_from_url(
                status_url_a, flight_number, departure_date, threshold
            )
            b = self._extract_from_url(
                status_url_b, flight_number, departure_date, threshold
            )
            if not a["date_match"] or not b["date_match"]:
                raise gl.vm.UserError("evidence is not bound to the policy departure date")
            if a["status"] != b["status"]:
                raise gl.vm.UserError("independent sources disagree on flight status")
            delay_delta = a["delay_minutes"] - b["delay_minutes"]
            if delay_delta < 0:
                delay_delta = -delay_delta
            if delay_delta > 15:
                raise gl.vm.UserError("independent sources disagree on delay")
            delay_minutes = a["delay_minutes"]
            if b["delay_minutes"] > delay_minutes:
                delay_minutes = b["delay_minutes"]
            result = {
                "date_match": True,
                "delay_minutes": delay_minutes,
                "status": a["status"],
            }
            return json.dumps(result, sort_keys=True, separators=(",", ":"))

        result = json.loads(gl.eq_principle.strict_eq(fetch_and_corroborate))
        delay_minutes = result["delay_minutes"]
        observed_status = result["status"]
        date_match = bool(result["date_match"])

        eligible = date_match and (
            observed_status == "CANCELLED"
            or (observed_status == "DELAYED" and delay_minutes >= threshold)
        )

        policy.observed_delay_minutes = delay_minutes
        policy.observed_status = observed_status
        policy.observed_date_match = date_match
        policy.payout_eligible = eligible
        policy.reserved = 0
        self.reserved_coverage = self.reserved_coverage - coverage

        if eligible:
            policy.status = "APPROVED"
            policy.premium_disposition = "PAID_AS_COVERAGE"
            _Recipient(policyholder).emit_transfer(value=coverage)
        else:
            policy.status = "REJECTED"
            policy.premium_disposition = "RETAINED_BY_CONTRACT"
            self.retained_premiums = self.retained_premiums + coverage

    @gl.public.view
    def get_policy(self, policy_id: str) -> str:
        if policy_id not in self.policies:
            raise gl.vm.UserError("policy not found")
        policy = self.policies[policy_id]
        return json.dumps(
            {
                "policy_id": policy_id,
                "policyholder": policy.policyholder.as_hex,
                "flight_number": policy.flight_number,
                "departure_date": policy.departure_date,
                "delay_threshold_minutes": int(policy.delay_threshold_minutes),
                "status_url_a": policy.status_url_a,
                "status_url_b": policy.status_url_b,
                "premium": int(policy.premium),
                "coverage": int(policy.coverage),
                "reserved": int(policy.reserved),
                "status": policy.status,
                "observed_delay_minutes": int(policy.observed_delay_minutes),
                "observed_status": policy.observed_status,
                "observed_date_match": policy.observed_date_match,
                "payout_eligible": policy.payout_eligible,
                "premium_disposition": policy.premium_disposition,
            },
            sort_keys=True,
        )

    @gl.public.view
    def get_policy_status(self, policy_id: str) -> str:
        if policy_id not in self.policies:
            raise gl.vm.UserError("policy not found")
        return self.policies[policy_id].status

    @gl.public.view
    def get_policy_count(self) -> u256:
        return self.next_policy_id - 1

    @gl.public.view
    def get_reserved_coverage(self) -> u256:
        return self.reserved_coverage

    @gl.public.view
    def get_retained_premiums(self) -> u256:
        return self.retained_premiums
