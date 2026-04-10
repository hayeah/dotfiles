package supervisor

import (
	"encoding/json"
	"testing"
	"time"
)

func TestEventBusPubSub(t *testing.T) {
	bus := NewEventBus()
	defer bus.Close()

	ch, unsub := bus.Subscribe()
	defer unsub()

	// Publish an event
	ev := Event{Type: "state", Data: json.RawMessage(`{"key":"vite"}`)}
	bus.Publish(ev)

	select {
	case received := <-ch:
		if received.Type != "state" {
			t.Errorf("got type=%s, want state", received.Type)
		}
	case <-time.After(time.Second):
		t.Fatal("timed out waiting for event")
	}
}

func TestEventBusSnapshot(t *testing.T) {
	bus := NewEventBus()
	defer bus.Close()

	// Publish a state event before subscribing
	bus.Publish(Event{Type: "state", Data: json.RawMessage(`{"cached":true}`)})

	// New subscriber should get the cached state as a snapshot
	ch, unsub := bus.Subscribe()
	defer unsub()

	select {
	case received := <-ch:
		if received.Type != "snapshot" {
			t.Errorf("got type=%s, want snapshot", received.Type)
		}
	case <-time.After(time.Second):
		t.Fatal("timed out waiting for snapshot")
	}
}

func TestEventBusMultipleSubscribers(t *testing.T) {
	bus := NewEventBus()
	defer bus.Close()

	ch1, unsub1 := bus.Subscribe()
	defer unsub1()
	ch2, unsub2 := bus.Subscribe()
	defer unsub2()

	bus.Publish(Event{Type: "state", Data: json.RawMessage(`{"n":1}`)})

	for _, ch := range []<-chan Event{ch1, ch2} {
		select {
		case ev := <-ch:
			if ev.Type != "state" {
				t.Errorf("got type=%s, want state", ev.Type)
			}
		case <-time.After(time.Second):
			t.Fatal("timed out")
		}
	}
}

func TestEventBusClose(t *testing.T) {
	bus := NewEventBus()
	ch, _ := bus.Subscribe()
	bus.Close()

	// Channel should be closed
	_, ok := <-ch
	if ok {
		t.Fatal("expected channel to be closed after bus.Close()")
	}
}
