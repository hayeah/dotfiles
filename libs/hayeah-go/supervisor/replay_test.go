package supervisor

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
	"testing"
	"time"
)

// sequencedPlugin emits a fixed sequence of state values via UpdateService.
// Used to drive the supervisor's idle-edge detection deterministically.
type sequencedPlugin struct {
	states []string
	period time.Duration
}

func (p *sequencedPlugin) Run(ctx context.Context, env PluginEnv) error {
	type svc struct {
		State string `json:"state"`
	}
	for _, s := range p.states {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(p.period):
		}
		if err := env.UpdateService(svc{State: s}); err != nil {
			return err
		}
	}
	<-ctx.Done()
	return ctx.Err()
}

// TestSupervisorReplaysBriefingsInSequence walks the supervisor through
// two idle transitions with a Briefings list of two messages, and checks
// that both messages land in the tmux pane in order. The pane runs `cat`,
// which echoes whatever text we send into it, so the messages show up
// verbatim.
//
// Timing model: the plugin emits working/idle/working/idle every 200ms.
// sendBriefingMessage sleeps 500ms before each send to let the input box
// settle. Allow ~5s budget to absorb tmux startup variance.
func TestSupervisorReplaysBriefingsInSequence(t *testing.T) {
	if _, err := exec.LookPath("tmux"); err != nil {
		t.Skip("tmux not found")
	}
	if _, err := exec.LookPath("cat"); err != nil {
		t.Skip("cat not found")
	}

	stateDir := t.TempDir()
	session := fmt.Sprintf("supreplay-%d", time.Now().UnixNano())
	t.Cleanup(func() {
		_ = exec.Command("tmux", "kill-session", "-t", session).Run()
	})

	plugin := &sequencedPlugin{
		states: []string{"working", "idle", "working", "idle"},
		period: 200 * time.Millisecond,
	}

	sup := New(SupervisorConfig{
		StateDir: stateDir,
		Key:      "test",
		Spawn: TmuxSpawn{
			Session: session,
			Window:  "test",
			Cmd:     []string{"cat"},
		},
		Plugin:    plugin,
		Briefings: []string{"hello-one-msg", "hello-two-msg"},
	})

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	done := make(chan error, 1)
	go func() { done <- sup.Run(ctx) }()

	target := session + ":test"
	deadline := time.Now().Add(8 * time.Second)
	var content string
	for time.Now().Before(deadline) {
		out, err := exec.Command("tmux", "capture-pane", "-p", "-t", target, "-S", "-200").Output()
		if err == nil {
			content = string(out)
			if strings.Contains(content, "hello-one-msg") && strings.Contains(content, "hello-two-msg") {
				break
			}
		}
		time.Sleep(150 * time.Millisecond)
	}

	if !strings.Contains(content, "hello-one-msg") {
		t.Fatalf("missing hello-one-msg in pane content:\n%s", content)
	}
	if !strings.Contains(content, "hello-two-msg") {
		t.Fatalf("missing hello-two-msg in pane content:\n%s", content)
	}

	// Ordering: hello-one must appear before hello-two.
	idx1 := strings.Index(content, "hello-one-msg")
	idx2 := strings.Index(content, "hello-two-msg")
	if idx1 < 0 || idx2 < 0 || idx2 < idx1 {
		t.Fatalf("messages out of order (idx1=%d, idx2=%d):\n%s", idx1, idx2, content)
	}

	cancel()
	select {
	case <-done:
	case <-time.After(3 * time.Second):
		t.Errorf("supervisor did not exit within 3s of cancel")
	}
}

// TestSupervisorIgnoresIdleEdgeAfterAllBriefingsSent verifies that extra
// idle transitions beyond len(Briefings) don't crash and don't re-send
// messages.
func TestSupervisorIgnoresIdleEdgeAfterAllBriefingsSent(t *testing.T) {
	if _, err := exec.LookPath("tmux"); err != nil {
		t.Skip("tmux not found")
	}

	stateDir := t.TempDir()
	session := fmt.Sprintf("supreplay-extra-%d", time.Now().UnixNano())
	t.Cleanup(func() {
		_ = exec.Command("tmux", "kill-session", "-t", session).Run()
	})

	plugin := &sequencedPlugin{
		// Two idle edges; only one briefing message → second edge should
		// be a no-op (no panic, no extra send).
		states: []string{"working", "idle", "working", "idle"},
		period: 150 * time.Millisecond,
	}

	sup := New(SupervisorConfig{
		StateDir:  stateDir,
		Key:       "test",
		Spawn:     TmuxSpawn{Session: session, Window: "test", Cmd: []string{"cat"}},
		Plugin:    plugin,
		Briefings: []string{"only-msg"},
	})

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	done := make(chan error, 1)
	go func() { done <- sup.Run(ctx) }()

	// Wait long enough for both edges + the 500ms send delay.
	time.Sleep(2 * time.Second)

	out, _ := exec.Command("tmux", "capture-pane", "-p", "-t", session+":test", "-S", "-200").Output()
	content := string(out)
	if !strings.Contains(content, "only-msg") {
		t.Fatalf("missing only-msg in pane content:\n%s", content)
	}
	if strings.Count(content, "only-msg") > 2 {
		// Cat echoes once; if we sent it twice we'd see it 4+ times
		// (typed line + echoed line, twice). Cap the threshold loosely.
		t.Fatalf("only-msg appeared %d times — looks like duplicate send:\n%s",
			strings.Count(content, "only-msg"), content)
	}

	cancel()
	select {
	case <-done:
	case <-time.After(3 * time.Second):
		t.Errorf("supervisor did not exit within 3s of cancel")
	}
}
