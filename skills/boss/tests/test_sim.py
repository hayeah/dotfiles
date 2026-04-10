from boss import sim


def test_ensure_simulator_reuses_preferred_udid(monkeypatch):
    leased: list[tuple[str, str]] = []
    booted: list[str] = []

    monkeypatch.setattr(sim, "_device_by_udid", lambda udid: {"udid": udid, "name": "agentboss-000"})
    monkeypatch.setattr(sim.agentboss, "lease_check", lambda resource: None)
    monkeypatch.setattr(sim.agentboss, "lease", lambda key, resource: leased.append((key, resource)))
    monkeypatch.setattr(sim, "_boot", lambda udid: booted.append(udid))

    udid = sim.ensure_simulator("agent-1", preferred_udid="SIM-123")

    assert udid == "SIM-123"
    assert leased == [("agent-1", "simulator:SIM-123")]
    assert booted == ["SIM-123"]


def test_release_simulator_uses_live_holder(monkeypatch):
    released: list[tuple[str, str]] = []
    shutdowns: list[tuple[str, ...]] = []

    monkeypatch.setattr(sim.agentboss, "lease_check", lambda resource: "agent-9")
    monkeypatch.setattr(sim.agentboss, "lease_release", lambda key, resource: released.append((key, resource)))
    monkeypatch.setattr(
        sim,
        "sh",
        lambda *args, **kwargs: shutdowns.append(tuple(str(a) for a in args)),
    )

    sim.release_simulator("SIM-999")

    assert released == [("agent-9", "simulator:SIM-999")]
    assert shutdowns == [("xcrun", "simctl", "shutdown", "SIM-999")]
