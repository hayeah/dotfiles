// Package logger provides structured logging with dual output:
// colored console on stderr and JSONL file with rotation.
package logger

import (
	"context"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/lmittmann/tint"
	"golang.org/x/term"
	"gopkg.in/natefinch/lumberjack.v2"
)

var (
	loggers sync.Map // map[string]*slog.Logger
)

// New returns a named logger. Repeated calls with the same name return the
// same instance. The logger fans out to a colored console handler on stderr
// and a JSONL file handler at ~/.local/log/<name>.jsonl.
func New(name string) *slog.Logger {
	if l, ok := loggers.Load(name); ok {
		return l.(*slog.Logger)
	}

	level := parseLevel(os.Getenv("LOG_LEVEL"))

	// Console handler (tint) on stderr
	consoleHandler := tint.NewHandler(os.Stderr, &tint.Options{
		Level:   level,
		NoColor: !isTTY(),
	})

	// File handler (JSON) with rotation
	logDir := filepath.Join(os.Getenv("HOME"), ".local", "log")
	_ = os.MkdirAll(logDir, 0o755)

	fileWriter := &lumberjack.Logger{
		Filename:   filepath.Join(logDir, name+".jsonl"),
		MaxSize:    5, // MB
		MaxBackups: 3,
	}

	fileHandler := slog.NewJSONHandler(fileWriter, &slog.HandlerOptions{
		Level: level,
	})

	// Combine both handlers
	multi := &multiHandler{handlers: []slog.Handler{consoleHandler, fileHandler}}
	l := slog.New(multi).With("logger", name)

	actual, _ := loggers.LoadOrStore(name, l)
	return actual.(*slog.Logger)
}

func parseLevel(s string) slog.Level {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "debug":
		return slog.LevelDebug
	case "warn", "warning":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

func isTTY() bool {
	return term.IsTerminal(int(os.Stderr.Fd()))
}

// multiHandler fans out log records to multiple handlers.
type multiHandler struct {
	handlers []slog.Handler
}

func (h *multiHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, handler := range h.handlers {
		if handler.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

func (h *multiHandler) Handle(ctx context.Context, r slog.Record) error {
	for _, handler := range h.handlers {
		if handler.Enabled(ctx, r.Level) {
			if err := handler.Handle(ctx, r); err != nil {
				return err
			}
		}
	}
	return nil
}

func (h *multiHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	handlers := make([]slog.Handler, len(h.handlers))
	for i, handler := range h.handlers {
		handlers[i] = handler.WithAttrs(attrs)
	}
	return &multiHandler{handlers: handlers}
}

func (h *multiHandler) WithGroup(name string) slog.Handler {
	handlers := make([]slog.Handler, len(h.handlers))
	for i, handler := range h.handlers {
		handlers[i] = handler.WithGroup(name)
	}
	return &multiHandler{handlers: handlers}
}
