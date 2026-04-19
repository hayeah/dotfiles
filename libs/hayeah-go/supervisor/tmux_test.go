package supervisor

import (
	"reflect"
	"strings"
	"testing"
)

func TestEnvFlagsSortedOrder(t *testing.T) {
	env := map[string]string{
		"FOO":  "bar baz",
		"ZZZ":  "last",
		"AAA":  "first",
		"PORT": "20001",
	}
	got := envFlags(env)
	want := []string{
		"-e", "AAA=first",
		"-e", "FOO=bar baz",
		"-e", "PORT=20001",
		"-e", "ZZZ=last",
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("envFlags order wrong\n got=%v\nwant=%v", got, want)
	}
}

func TestEnvFlagsEmpty(t *testing.T) {
	if got := envFlags(nil); got != nil {
		t.Errorf("envFlags(nil) = %v; want nil", got)
	}
	if got := envFlags(map[string]string{}); got != nil {
		t.Errorf("envFlags(empty) = %v; want nil", got)
	}
}

// buildShellCmd must NOT prefix env exports anymore — env reaches the
// pane via tmux's native -e KEY=VAL args.
func TestBuildShellCmdDropsExports(t *testing.T) {
	tmux := &Tmux{}
	spawn := TmuxSpawn{
		Cmd: []string{"echo", "hello world"},
		Env: map[string]string{"FOO": "bar", "SECRET": "s p a c e"},
	}
	got := tmux.buildShellCmd(spawn)
	if strings.Contains(got, "export") {
		t.Errorf("buildShellCmd output still contains 'export': %q", got)
	}
	if !strings.Contains(got, "echo") {
		t.Errorf("buildShellCmd missing cmd: %q", got)
	}
}

// TmuxSpawn.Env values with literal spaces / quotes / newlines must pass
// through envFlags verbatim — that's the whole point of native -e fan-out.
func TestEnvFlagsLiteralValues(t *testing.T) {
	env := map[string]string{
		"SPACES":  "a b c",
		"QUOTES":  `a 'b' "c"`,
		"NEWLINE": "line1\nline2",
	}
	got := envFlags(env)
	// Values must appear verbatim as argv elements (no shell quoting).
	for i := 1; i < len(got); i += 2 {
		parts := strings.SplitN(got[i], "=", 2)
		if len(parts) != 2 {
			t.Fatalf("malformed -e value: %q", got[i])
		}
		k, v := parts[0], parts[1]
		want, ok := env[k]
		if !ok {
			t.Fatalf("unknown key %q", k)
		}
		if v != want {
			t.Errorf("key %q: got %q, want %q (must be literal)", k, v, want)
		}
	}
}
