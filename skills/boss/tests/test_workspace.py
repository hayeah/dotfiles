from boss import workspace


def test_create_preserves_existing_boss_json_extras(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))

    lay = workspace.create("ios-work", "iOS Work", "worktree")
    workspace.update_boss_json(
        lay.root,
        updates={
            "agent_id": "abc",
            "ios_simulator_udid": "SIM-123",
            "env": {"SWIFTUI_TAP_UDID": "SIM-123"},
        },
    )

    workspace.create("ios-work", "iOS Work", "worktree")

    data = workspace.read_boss_json(lay.root)
    assert data["slug"] == "ios-work"
    assert data["mode"] == "worktree"
    assert data["agent_id"] == "abc"
    assert data["ios_simulator_udid"] == "SIM-123"
    assert data["env"]["SWIFTUI_TAP_UDID"] == "SIM-123"
