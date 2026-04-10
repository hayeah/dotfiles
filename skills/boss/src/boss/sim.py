"""Lease-aware iOS simulator helpers."""

from __future__ import annotations

import json
import re

from . import agentboss
from .util import sh


DEFAULT_DEVICE_NAME = "iPhone 17 Pro"
MANAGED_PREFIX = "agentboss-"


class SimulatorError(Exception):
    pass


def simulator_resource(udid: str) -> str:
    return f"simulator:{udid}"


def _simctl_json(*args: str) -> dict:
    proc = sh("xcrun", "simctl", *args, "-j", check=False)
    if proc.returncode != 0:
        raise SimulatorError(proc.stderr.strip() or proc.stdout.strip())
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SimulatorError(f"invalid simctl json: {e}") from e


def _available_devices() -> list[dict]:
    payload = _simctl_json("list", "devices", "available")
    devices: list[dict] = []
    for runtime, runtime_devices in payload.get("devices", {}).items():
        for device in runtime_devices:
            if device.get("isAvailable", True):
                devices.append({**device, "runtime": runtime})
    return devices


def _device_by_udid(udid: str) -> dict | None:
    for device in _available_devices():
        if device.get("udid") == udid:
            return device
    return None


def _managed_devices() -> list[dict]:
    return sorted(
        (d for d in _available_devices() if d.get("name", "").startswith(MANAGED_PREFIX)),
        key=lambda d: d.get("name", ""),
    )


def _next_clone_name() -> str:
    highest = -1
    for device in _managed_devices():
        match = re.match(rf"^{re.escape(MANAGED_PREFIX)}(\d+)$", device.get("name", ""))
        if not match:
            continue
        highest = max(highest, int(match.group(1)))
    return f"{MANAGED_PREFIX}{highest + 1:03d}"


def _boot(udid: str) -> None:
    sh("xcrun", "simctl", "boot", udid, check=False)
    proc = sh("xcrun", "simctl", "bootstatus", udid, "-b", check=False)
    if proc.returncode != 0:
        raise SimulatorError(proc.stderr.strip() or proc.stdout.strip())


def _device_type_identifier(name: str) -> str:
    payload = _simctl_json("list", "devicetypes")
    for device_type in payload.get("devicetypes", []):
        if device_type.get("name") == name:
            identifier = device_type.get("identifier")
            if identifier:
                return identifier
    raise SimulatorError(f"no device type found for {name!r}")


def _clone(base_udid: str, clone_name: str) -> str:
    proc = sh("xcrun", "simctl", "clone", base_udid, clone_name, check=False)
    if proc.returncode != 0:
        raise SimulatorError(proc.stderr.strip() or proc.stdout.strip())
    udid = proc.stdout.strip()
    if not udid:
        raise SimulatorError(f"simctl clone {base_udid!r} returned no UDID")
    return udid


def _create(base_name: str, runtime: str) -> str:
    clone_name = _next_clone_name()
    device_type = _device_type_identifier(base_name)
    proc = sh("xcrun", "simctl", "create", clone_name, device_type, runtime, check=False)
    if proc.returncode != 0:
        raise SimulatorError(proc.stderr.strip() or proc.stdout.strip())
    udid = proc.stdout.strip()
    if not udid:
        raise SimulatorError(f"simctl create {base_name!r} returned no UDID")
    return udid


def _allocate_new(base_name: str) -> str:
    matches = [device for device in _available_devices() if device.get("name") == base_name]
    if not matches:
        raise SimulatorError(f"no available simulator named {base_name!r}")

    clone_name = _next_clone_name()
    shutdown_base = next((device for device in matches if device.get("state") != "Booted"), None)
    if shutdown_base is not None:
        try:
            return _clone(shutdown_base["udid"], clone_name)
        except SimulatorError:
            pass

    runtime = matches[0].get("runtime")
    if not runtime:
        raise SimulatorError(f"missing runtime for simulator {base_name!r}")
    return _create(base_name, runtime)


def ensure_simulator(agent_id: str, preferred_udid: str | None = None, base_name: str = DEFAULT_DEVICE_NAME) -> str:
    """Return a booted simulator UDID leased to this agent."""
    if preferred_udid:
        device = _device_by_udid(preferred_udid)
        if device is not None:
            holder = agentboss.lease_check(simulator_resource(preferred_udid))
            if holder in (None, agent_id):
                if holder is None:
                    agentboss.lease(agent_id, simulator_resource(preferred_udid))
                _boot(preferred_udid)
                return preferred_udid

    for device in _managed_devices():
        udid = device.get("udid")
        if not udid:
            continue
        holder = agentboss.lease_check(simulator_resource(udid))
        if holder not in (None, agent_id):
            continue
        if holder is None:
            agentboss.lease(agent_id, simulator_resource(udid))
        _boot(udid)
        return udid

    udid = _allocate_new(base_name)
    agentboss.lease(agent_id, simulator_resource(udid))
    _boot(udid)
    return udid


def release_simulator(udid: str, agent_id: str | None = None) -> None:
    holder = agent_id or agentboss.lease_check(simulator_resource(udid))
    if holder:
        try:
            agentboss.lease_release(holder, simulator_resource(udid))
        except agentboss.AgentbossError:
            pass
    sh("xcrun", "simctl", "shutdown", udid, check=False)
