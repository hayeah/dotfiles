package supervisor

import "testing"

func TestIsIdleState(t *testing.T) {
	type svc struct {
		State string `json:"state"`
		Since string `json:"since,omitempty"`
	}
	tests := []struct {
		name string
		val  any
		want bool
	}{
		{"idle state", svc{State: "idle"}, true},
		{"working state", svc{State: "working"}, false},
		{"empty state", svc{State: ""}, false},
		{"idle substring but different field", struct {
			Label string `json:"label"`
			State string `json:"state"`
		}{Label: "idle", State: "alive"}, false},
		{"nil", nil, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := isIdleState(tt.val); got != tt.want {
				t.Errorf("isIdleState(%+v) = %v, want %v", tt.val, got, tt.want)
			}
		})
	}
}

func TestPluginForCycle(t *testing.T) {
	called := 0
	factory := func() Plugin {
		called++
		return nil
	}
	s := &Runner{cfg: SupervisorConfig{PluginFactory: factory}}
	for i := 0; i < 3; i++ {
		s.pluginForCycle(i)
	}
	if called != 3 {
		t.Errorf("factory called %d times, want 3", called)
	}

	// Without a factory, falls through to Plugin field.
	s2 := &Runner{cfg: SupervisorConfig{}}
	if p := s2.pluginForCycle(0); p != nil {
		t.Errorf("want nil plugin when neither factory nor Plugin set")
	}
}
