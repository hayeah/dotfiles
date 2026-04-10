from pathlib import Path

from typer.testing import CliRunner

from boss import main, workspace


def test_checkout_ios_simulator_updates_workspace_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path / "boss-root"))

    lay = workspace.create("ios-work", "iOS Work", "worktree")
    workspace.update_boss_json(lay.root, updates={"agent_id": "agent-1"})

    repo = tmp_path / "github.com" / "hayeah" / "reader-swiftui"
    repo.mkdir(parents=True)

    monkeypatch.chdir(lay.root)
    monkeypatch.setattr(main.sim, "ensure_simulator", lambda agent_id, preferred_udid=None: "SIM-123")

    result = CliRunner().invoke(main.app, ["checkout", str(repo), "--no-tree", "--ios-simulator"])

    assert result.exit_code == 0, result.output
    assert "ios simulator: SIM-123" in result.output
    assert "export SWIFTUI_TAP_UDID=SIM-123" in result.output

    data = workspace.read_boss_json(lay.root)
    assert data["ios_simulator_udid"] == "SIM-123"
    assert data["env"]["SWIFTUI_TAP_UDID"] == "SIM-123"
    assert (lay.repos / Path("github.com/hayeah/reader-swiftui")).is_symlink()
