# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass

from genlayer import *


@allow_storage
@dataclass
class FlightPolicy:
    policyholder: Address
    flight_number: str
    delay_threshold_minutes: u32
    status_url: str
    premium: u256
    status: str
    observed_delay_minutes: i32
    observed_status: str
    payout_eligible: bool


class ParametricFlightInsurance(gl.Contract):
    policies: TreeMap[str, FlightPolicy]
    next_policy_id: u256

    def __init__(self):
        self.next_policy_id = 1

    @gl.public.write.payable
    def create_policy(
        self,
        flight_number: str,
        delay_threshold_minutes: u32,
        status_url: str,
    ) -> str:
        if not flight_number.strip():
            raise gl.vm.UserError("flight number is required")
        if delay_threshold_minutes == 0:
            raise gl.vm.UserError("delay threshold must be greater than zero")
        if not status_url.startswith(("https://", "http://")):
            raise gl.vm.UserError("status URL must use http or https")

        premium = gl.message.value
        if premium == 0:
            raise gl.vm.UserError("a non-zero premium is required")

        policy_id = str(self.next_policy_id)
        self.policies[policy_id] = FlightPolicy(
            policyholder=gl.message.sender_address,
            flight_number=flight_number.strip().upper(),
            delay_threshold_minutes=delay_threshold_minutes,
            status_url=status_url,
            premium=premium,
            status="ACTIVE",
            observed_delay_minutes=-1,
            observed_status="UNRESOLVED",
            payout_eligible=False,
        )
        self.next_policy_id = self.next_policy_id + 1
        return policy_id

    @gl.public.write
    def resolve(self, policy_id: str) -> None:
        policy = self.policies[policy_id]
        if policy.status != "ACTIVE":
            raise gl.vm.UserError("policy has already been resolved")

        # Copy storage fields to memory before entering the nondeterministic block.
        status_url = policy.status_url
        flight_number = policy.flight_number
        threshold = policy.delay_threshold_minutes
        policyholder = policy.policyholder
        premium = policy.premium

        def fetch_and_extract() -> str:
            page = gl.nondet.web.get(status_url)
            page_text = page.body.decode("utf-8")
            prompt = f"""
You are extracting an insurance decision from a public flight status page.
Flight number: {flight_number}
Delay threshold in minutes: {threshold}
Page content:
{page_text}

Return JSON only, with exactly these fields:
{{"delay_minutes": integer, "status": "ON_TIME"|"DELAYED"|"CANCELLED"|"UNKNOWN"}}
Use the currently reported departure delay in minutes. Use 0 when the page
clearly says the flight is on time. Use -1 when no delay can be established.
Use CANCELLED only when the page explicitly says the flight is cancelled.
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
            return json.dumps(result, sort_keys=True, separators=(",", ":"))

        # Canonical JSON makes strict equality compare only the objective fields.
        result = json.loads(gl.eq_principle.strict_eq(fetch_and_extract))
        delay_minutes = result["delay_minutes"]
        observed_status = result["status"]
        eligible = observed_status == "CANCELLED" or (
            delay_minutes >= threshold
        )

        policy.status = "APPROVED" if eligible else "REJECTED"
        policy.observed_delay_minutes = delay_minutes
        policy.observed_status = observed_status
        policy.payout_eligible = eligible

        if eligible:
            # The premium is also the policy payout. Keep the transfer atomic with
            # the state update so a failed transfer cannot leave a paid claim.
            _Recipient(policyholder).emit_transfer(value=premium)

    @gl.public.view
    def get_policy(self, policy_id: str) -> dict[str, object]:
        policy = self.policies[policy_id]
        return {
            "policy_id": policy_id,
            "policyholder": policy.policyholder.as_hex,
            "flight_number": policy.flight_number,
            "delay_threshold_minutes": policy.delay_threshold_minutes,
            "status_url": policy.status_url,
            "premium": policy.premium,
            "status": policy.status,
            "observed_delay_minutes": policy.observed_delay_minutes,
            "observed_status": policy.observed_status,
            "payout_eligible": policy.payout_eligible,
        }

    @gl.public.view
    def get_policy_status(self, policy_id: str) -> str:
        return self.policies[policy_id].status

    @gl.public.view
    def get_policy_count(self) -> u256:
        return self.next_policy_id - 1