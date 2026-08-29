# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
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
    "flightaware.com",
    "www.google.com",
    "www.bing.com",
    "www.kayak.com",
    "www.expedia.com",
    "www.aa.com",
    "www.united.com",
    "www.delta.com",
    "www.ba.com",
    "www.britishairways.com",
    "www.lufthansa.com",
)


@allow_storage
@dataclass
class FlightPolicy:
    policyholder: Address
    flight_number: str
    delay_threshold_minutes: u32
    status_url_a: str
    status_url_b: str
    premium: u256
    reserved: u256
    status: str
    observed_delay_minutes: i32
    observed_status: str
    payout_eligible: bool
    premium_disposition: str


class ParametricFlightInsurance(gl.Contract):
    policies: TreeMap[str, FlightPolicy]
    next_policy_id: u256
    reserved_premiums: u256

    def __init__(self):
        self.next_policy_id = 1
        self.reserved_premiums = 0

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

    def _extract_from_url(self, status_url: str, flight_number: str, threshold: u32) -> dict:
        page = gl.nondet.web.get(status_url)
        page_text = page.body.decode("utf-8")[:6000]
        prompt = f"""
You are extracting flight facts from a trusted public flight status page.
Flight number: {flight_number}
Delay threshold in minutes: {threshold}
Page URL: {status_url}
Page content:
{page_text}

Return JSON only, with exactly these fields:
{{"delay_minutes": integer, "status": "ON_TIME"|"DELAYED"|"CANCELLED"|"UNKNOWN"}}
Use the currently reported departure delay in minutes.
Use 0 when the page clearly says the flight is on time.
Use -1 when no delay can be established.
Use CANCELLED only when the page explicitly says the flight is cancelled.
Use UNKNOWN when the page does not clearly identify this flight.
"""
        extracted = json.loads(gl.nondet.exec_prompt(prompt))
        result = {
            "delay_minutes": int(extracted["delay_minutes"]),
            "status": str(extracted["status"]).upper(),
        }
        if result["status"] not in ("ON_TIME", "DELAYED", "CANCELLED", "UNKNOWN"):
            raise gl.vm.UserError("flight status could not be classified")
        if result["delay_minutes"] < -1:
            raise gl.vm.UserError("invalid delay value")
        return result

    @gl.public.write.payable
    def create_policy(
        self,
        flight_number: str,
        delay_threshold_minutes: u32,
        status_url_a: str,
        status_url_b: str,
    ) -> str:
        if not flight_number.strip():
            raise gl.vm.UserError("flight number is required")
        if delay_threshold_minutes == 0:
            raise gl.vm.UserError("delay threshold must be greater than zero")

        self._assert_trusted_url(status_url_a)
        self._assert_trusted_url(status_url_b)
        if self._host(status_url_a) == self._host(status_url_b):
            raise gl.vm.UserError("the two status URLs must come from different hosts")

        premium = gl.message.value
        if premium == 0:
            raise gl.vm.UserError("a non-zero premium is required")

        policy_id = str(self.next_policy_id)
        self.policies[policy_id] = FlightPolicy(
            policyholder=gl.message.sender_address,
            flight_number=flight_number.strip().upper(),
            delay_threshold_minutes=delay_threshold_minutes,
            status_url_a=status_url_a,
            status_url_b=status_url_b,
            premium=premium,
            reserved=premium,
            status="ACTIVE",
            observed_delay_minutes=-1,
            observed_status="UNRESOLVED",
            payout_eligible=False,
            premium_disposition="RESERVED",
        )
        self.reserved_premiums = self.reserved_premiums + premium
        self.next_policy_id = self.next_policy_id + 1
        return policy_id

    @gl.public.write
    def resolve(self, policy_id: str) -> None:
        policy = self.policies[policy_id]
        if policy.status != "ACTIVE":
            raise gl.vm.UserError("policy has already been resolved")
        if policy.reserved != policy.premium:
            raise gl.vm.UserError("policy reserve is inconsistent")
        if self.balance < policy.reserved:
            raise gl.vm.UserError("contract is not solvent for this payout or refund")

        status_url_a = policy.status_url_a
        status_url_b = policy.status_url_b
        flight_number = policy.flight_number
        threshold = policy.delay_threshold_minutes
        policyholder = policy.policyholder
        premium = policy.premium

        def fetch_and_corroborate() -> str:
            a = self._extract_from_url(status_url_a, flight_number, threshold)
            b = self._extract_from_url(status_url_b, flight_number, threshold)
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
                "delay_minutes": delay_minutes,
                "status": a["status"],
            }
            return json.dumps(result, sort_keys=True, separators=(",", ":"))

        result = json.loads(gl.eq_principle.strict_eq(fetch_and_corroborate))
        delay_minutes = result["delay_minutes"]
        observed_status = result["status"]

        # ON_TIME and UNKNOWN can never qualify through the delay field.
        eligible = observed_status == "CANCELLED" or (
            observed_status == "DELAYED" and delay_minutes >= threshold
        )

        policy.observed_delay_minutes = delay_minutes
        policy.observed_status = observed_status
        policy.payout_eligible = eligible
        policy.reserved = 0
        self.reserved_premiums = self.reserved_premiums - premium

        if eligible:
            policy.status = "APPROVED"
            policy.premium_disposition = "PAID_TO_POLICYHOLDER"
            _Recipient(policyholder).emit_transfer(value=premium)
        else:
            policy.status = "REJECTED"
            policy.premium_disposition = "REFUNDED_TO_POLICYHOLDER"
            _Recipient(policyholder).emit_transfer(value=premium)

    @gl.public.view
    def get_policy(self, policy_id: str) -> str:
        policy = self.policies[policy_id]
        return json.dumps(
            {
                "policy_id": policy_id,
                "policyholder": policy.policyholder.as_hex,
                "flight_number": policy.flight_number,
                "delay_threshold_minutes": int(policy.delay_threshold_minutes),
                "status_url_a": policy.status_url_a,
                "status_url_b": policy.status_url_b,
                "premium": int(policy.premium),
                "reserved": int(policy.reserved),
                "status": policy.status,
                "observed_delay_minutes": int(policy.observed_delay_minutes),
                "observed_status": policy.observed_status,
                "payout_eligible": policy.payout_eligible,
                "premium_disposition": policy.premium_disposition,
            },
            sort_keys=True,
        )

    @gl.public.view
    def get_policy_status(self, policy_id: str) -> str:
        return self.policies[policy_id].status

    @gl.public.view
    def get_policy_count(self) -> u256:
        return self.next_policy_id - 1

    @gl.public.view
    def get_reserved_premiums(self) -> u256:
        return self.reserved_premiums