package supervisor

import (
	"encoding/json"
	"sync"
)

// Event represents a state change or lifecycle event.
type Event struct {
	Type string          `json:"type"` // "state", "exited", "snapshot"
	Data json.RawMessage `json:"data"`
}

// EventBus is an in-memory pub/sub for supervisor events.
// New subscribers receive the cached last-state event immediately.
type EventBus struct {
	mu          sync.RWMutex
	subscribers map[*subscriber]struct{}
	lastState   *Event
	closed      bool
}

type subscriber struct {
	ch chan Event
}

func NewEventBus() *EventBus {
	return &EventBus{
		subscribers: make(map[*subscriber]struct{}),
	}
}

// Publish sends an event to all subscribers. Slow subscribers get events
// dropped (non-blocking send on buffered channel).
func (b *EventBus) Publish(ev Event) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		return
	}
	if ev.Type == "state" {
		b.lastState = &ev
	}
	for sub := range b.subscribers {
		select {
		case sub.ch <- ev:
		default:
			// slow subscriber — drop event
		}
	}
}

// Subscribe returns a channel that receives events and an unsubscribe
// function. The caller receives the cached last-state immediately (as a
// "snapshot" event) if one exists.
func (b *EventBus) Subscribe() (<-chan Event, func()) {
	b.mu.Lock()
	defer b.mu.Unlock()

	sub := &subscriber{ch: make(chan Event, 64)}
	b.subscribers[sub] = struct{}{}

	// Send cached last-state as snapshot
	if b.lastState != nil {
		snapshot := Event{Type: "snapshot", Data: b.lastState.Data}
		select {
		case sub.ch <- snapshot:
		default:
		}
	}

	unsub := func() {
		b.mu.Lock()
		defer b.mu.Unlock()
		delete(b.subscribers, sub)
		close(sub.ch)
	}
	return sub.ch, unsub
}

// Close shuts down the bus and closes all subscriber channels.
func (b *EventBus) Close() {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.closed = true
	for sub := range b.subscribers {
		close(sub.ch)
		delete(b.subscribers, sub)
	}
}
