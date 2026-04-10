package supervisor

import (
	"encoding/json"
	"time"
)

// StateFile is the root of state.json. Two namespaced sections:
// supervisor (owned by the supervisor) and service (owned by the plugin).
type StateFile struct {
	Supervisor SupervisorState `json:"supervisor"`
	Service    json.RawMessage `json:"service,omitempty"`
}

// SupervisorState is written by the supervisor library. The plugin never
// touches it. This is purely the supervisor's own bookkeeping.
type SupervisorState struct {
	Key       string    `json:"key"`
	Spawn     TmuxSpawn `json:"spawn"`
	CreatedAt time.Time `json:"created_at"`
}
