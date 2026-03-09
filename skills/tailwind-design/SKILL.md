---
name: tailwind
description: Design tokens and component patterns for Tailwind CSS projects.
globs:
  - tailwind.config.*
  - "**/*.css"
  - "**/*.tsx"
  - "**/*.jsx"
---

# Tailwind Design Tokens

Style guide for building with Tailwind CSS using centralized design tokens. The core principle: name design decisions once, reference them everywhere, separate meaning from appearance.

## Three-Layer Token Model

- **Raw tokens** - primitive values: color palettes, spacing scale, radius scale, font scale
  - Example: `blue-600 = #2563eb`, `radius-md = 8px`
- **Semantic tokens** - meaning-based names mapped to raw tokens
  - Example: `color.primary = blue-600`
  - Components should mostly use semantic tokens
- **Component tokens** (optional) - component-specific aliases built from semantic tokens
  - Example: `button.background.primary = color.primary`
  - Useful in large systems

In Tailwind, raw and semantic tokens live in `tailwind.config`, and semantic tokens reference CSS variables for theming.

## What Should Be a Token

Tokenize values that:

- Appear in many places
- Encode brand or design language
- Are likely to change globally
- Should be constrained to avoid one-off values

At minimum, centralize: **colors, radius, shadows, typography**.

Other common categories: spacing, font weights, z-index layers, motion durations/easing, breakpoints.

## Semantic Colors via CSS Variables

Define semantic colors referencing CSS variables in `tailwind.config`:

```ts
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: "hsl(var(--primary))",
        "primary-foreground": "hsl(var(--primary-foreground))",
        secondary: "hsl(var(--secondary))",
        "secondary-foreground": "hsl(var(--secondary-foreground))",
        muted: "hsl(var(--muted))",
        "muted-foreground": "hsl(var(--muted-foreground))",
        destructive: "hsl(var(--destructive))",
        "destructive-foreground": "hsl(var(--destructive-foreground))",
        surface: "hsl(var(--surface))",
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
      },
    },
  },
}
```

Then define variables in `globals.css`:

```css
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 221.2 83.2% 53.3%;
  --primary-foreground: 210 40% 98%;
  /* ... */
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --primary: 217.2 91.2% 59.8%;
  --primary-foreground: 222.2 47.4% 11.2%;
  /* ... */
}
```

Why CSS variables:
- Theme switching changes variables, not Tailwind rebuild
- Light/dark becomes automatic
- Brand themes can be swapped dynamically

## Semantic Color Taxonomy

Name colors by **role**, not appearance.

Bad: `bg-blue-600`, `text-gray-800`

Good: `bg-primary`, `bg-surface`, `text-foreground`, `text-muted-foreground`

Standard semantic set:
- `background` / `foreground` - page-level
- `surface` - card/panel backgrounds
- `muted` / `muted-foreground` - subdued elements
- `primary` / `primary-foreground` - primary actions
- `secondary` / `secondary-foreground` - secondary actions
- `destructive` / `destructive-foreground` - danger/delete
- `border` / `input` / `ring` - form and focus states

## No Arbitrary Values

Avoid:
- `text-[#1f2937]` - use a semantic color token
- `rounded-[10px]` - use a radius token
- `shadow-[0_3px_12px_rgba(...)]` - use a shadow token
- `p-[13px]`, `mt-[7px]` - use the spacing scale

If you need a value twice, make it a token.

## Radius and Shadow as Elevation

Define constrained scales in config:

```ts
borderRadius: {
  sm: "4px",
  md: "8px",
  lg: "12px",
  xl: "16px",
},
boxShadow: {
  sm: "0 1px 2px 0 rgb(0 0 0 / 0.05)",     // subtle
  md: "0 4px 6px -1px rgb(0 0 0 / 0.1)",    // card
  lg: "0 10px 15px -3px rgb(0 0 0 / 0.1)",  // modal
},
```

Components use `rounded-md`, `shadow-sm`, `shadow-lg`. Changing visual style means changing token values, not component code.

## Typography Tokens

Standardize allowed text sizes. Optionally define semantic font utilities:

```ts
fontSize: {
  caption: ["0.75rem", { lineHeight: "1rem" }],
  body: ["0.875rem", { lineHeight: "1.25rem" }],
  "heading-sm": ["1.125rem", { lineHeight: "1.75rem", fontWeight: "600" }],
  "heading-lg": ["1.5rem", { lineHeight: "2rem", fontWeight: "700" }],
},
```

Usage: `text-body`, `text-caption`, `text-heading-sm`. Prevents arbitrary `text-[15px]`.

## Spacing Discipline

Tailwind's spacing scale is already tokenized. The mistake is arbitrary spacing.

Encode spacing into component size variants:

```tsx
const sizeStyles = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-base",
  lg: "px-6 py-3 text-lg",
}
```

Spacing becomes part of the component API, not ad-hoc classes.

## Component Composition

Don't repeat class strings. Build components that consume tokens via variants.

```tsx
const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        ghost: "hover:bg-muted hover:text-muted-foreground",
        outline: "border border-input bg-background hover:bg-muted",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-base",
        lg: "h-12 px-6 text-lg",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
)
```

All variants reference semantic token utilities. If primary color changes, every button updates.

## Rules

- If a class combination appears twice, extract it into a component
- If an arbitrary value appears twice, make it a token
- No raw hex/rgb values in component files
- No arbitrary Tailwind values for tokenized categories (color, radius, shadow)
- Components reference only semantic utilities, never raw hue names like `bg-blue-600`
