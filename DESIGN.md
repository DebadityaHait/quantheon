# Quantheon workspace design

Quantheon is an operating workspace for derivatives traders and risk managers. The interface prioritizes reading and acting on financial information over decorative presentation.

## Visual language

The workspace uses a cool blue-grey surface scale with a darker, tinted navigation rail. Light and dark themes use the same semantic token names; color indicates selection, information, positive and negative values, or warnings. Density is controlled independently of theme. Inter Tight is used for interface text and JetBrains Mono for figures and technical values.

## Layout and components

Navigation is grouped by desk workflow. The desktop shell keeps navigation separate from the working area; narrow screens use a native page selector. Headers, panels, tables and metric tiles use restrained rules and surface contrast to establish hierarchy. Actions and forms use the shared primitives. On data-heavy screens, retain the established tabular layouts and clear numeric alignment rather than adding decorative cards.

## Implementation

The source of truth for colors, typography, spacing and motion is `frontend/src/tokens/`. Follow `frontend/UI_STYLE_GUIDE.md` for component, accessibility, responsive and density conventions. New interface work must work in light and dark themes and both density modes.
