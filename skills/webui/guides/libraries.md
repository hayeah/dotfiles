---
overview: Recommended libraries for React web UI projects — styling, icons, animation, interaction, data, charting, UI primitives.
tags:
  - guide
---

# Libraries

## Styling & Layout

- **Tailwind CSS v4** + `tailwindcss-animate` — primary styling. Use `@theme inline` in `index.css` for CSS variable tokens. OKLCh color space for theme values.
- **clsx** + **tailwind-merge** — combine via a `cn()` utility
- **class-variance-authority (cva)** — define component variants with constrained style sets
- **react-resizable-panels** — split-pane / resizable panel layouts

## Icons

- **lucide-react** — import individual icons: `import { BookOpen, ArrowDown } from 'lucide-react'`

## Animation

- **framer-motion** — entrance, scroll-triggered, layout, stagger, parallax. Use `motion.*`, `useScroll`, `useTransform`, `AnimatePresence`.

## Interaction

- **@dnd-kit** (core + sortable + modifiers) — drag and drop
- **cmdk** — command palette / search UI (Cmd+K pattern)
- **embla-carousel-react** — carousel / slider

## Data & Forms

- **zod** — schema validation
- **react-hook-form** + **@hookform/resolvers** — form state management with zod integration
- **input-otp** — OTP / PIN code input

## Charting & Visualization

- **recharts** — bar, line, area, pie charts. Compose with `<ResponsiveContainer>`, `<BarChart>`, etc.

## 3D

- **@react-three/fiber** + **@react-three/drei** + **three** — 3D scenes in React. Use sparingly for hero sections or decorative elements.

## UI Primitives

- **radix-ui** — headless accessible primitives (dialog, popover, dropdown, tabs, etc.)
- **vaul** — drawer / bottom sheet
- **sonner** — toast notifications
- **react-day-picker** + **date-fns** — calendar picker and date utilities
- **@headless-tree/react** — tree view / file browser

## State Management

- **mobx** + **mobx-react-lite** — see [MobX Global State Guide](mobx-global-state.md)

## Routing

- **wouter** — lightweight routing
