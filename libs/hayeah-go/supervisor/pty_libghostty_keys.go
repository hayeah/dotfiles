package supervisor

import (
	"strings"

	"code.selman.me/hauntty/libghostty"
)

// keyNameToCode translates a tmux-style key name (e.g. "Enter",
// "C-a", "M-Left", "hello") to a libghostty (KeyCode, Modifier)
// pair. Returns known=false if the name is a literal string to
// type (fall through to raw Write in SendKeys).
//
// Supported prefixes: C- (Ctrl), M- (Alt/Meta), S- (Shift). Stack
// freely: "C-M-Left", "S-Tab". Unknown base names return known=false.
func keyNameToCode(name string) (libghostty.KeyCode, libghostty.Modifier, bool) {
	var mods libghostty.Modifier
	s := name
	for {
		switch {
		case strings.HasPrefix(s, "C-"):
			mods |= libghostty.ModCtrl
			s = s[2:]
		case strings.HasPrefix(s, "M-"):
			mods |= libghostty.ModAlt
			s = s[2:]
		case strings.HasPrefix(s, "S-"):
			mods |= libghostty.ModShift
			s = s[2:]
		case strings.HasPrefix(s, "D-"):
			mods |= libghostty.ModSuper
			s = s[2:]
		default:
			goto lookup
		}
	}
lookup:
	if code, ok := namedKeys[s]; ok {
		return code, mods, true
	}
	// Single character + at least one modifier = treat as the
	// letter's KeyCode with modifiers. libghostty expects ASCII
	// letter keycodes in the 'a'..'z' range.
	if mods != 0 && len(s) == 1 {
		c := s[0]
		if c >= 'A' && c <= 'Z' {
			c = c + ('a' - 'A')
			mods |= libghostty.ModShift
		}
		return libghostty.KeyCode(c), mods, true
	}
	return 0, 0, false
}

// namedKeys maps symbolic key names to libghostty.KeyCode values.
// Names are a subset of tmux's vocabulary plus common synonyms
// (Esc / Escape, BSpace / Backspace).
var namedKeys = map[string]libghostty.KeyCode{
	"Enter":     libghostty.KeyEnter,
	"Return":    libghostty.KeyEnter,
	"Tab":       libghostty.KeyTab,
	"Escape":    libghostty.KeyEscape,
	"Esc":       libghostty.KeyEscape,
	"Backspace": libghostty.KeyBackspace,
	"BSpace":    libghostty.KeyBackspace,
	"Up":        libghostty.KeyUp,
	"Down":      libghostty.KeyDown,
	"Left":      libghostty.KeyLeft,
	"Right":     libghostty.KeyRight,
	"Home":      libghostty.KeyHome,
	"End":       libghostty.KeyEnd,
	"PageUp":    libghostty.KeyPageUp,
	"PPage":     libghostty.KeyPageUp,
	"PageDown":  libghostty.KeyPageDown,
	"NPage":     libghostty.KeyPageDown,
	"Insert":    libghostty.KeyInsert,
	"IC":        libghostty.KeyInsert,
	"Delete":    libghostty.KeyDelete,
	"DC":        libghostty.KeyDelete,
	"F1":        libghostty.KeyF1,
	"F2":        libghostty.KeyF2,
	"F3":        libghostty.KeyF3,
	"F4":        libghostty.KeyF4,
	"F5":        libghostty.KeyF5,
	"F6":        libghostty.KeyF6,
	"F7":        libghostty.KeyF7,
	"F8":        libghostty.KeyF8,
	"F9":        libghostty.KeyF9,
	"F10":       libghostty.KeyF10,
	"F11":       libghostty.KeyF11,
	"F12":       libghostty.KeyF12,
}
