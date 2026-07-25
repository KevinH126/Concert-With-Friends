import { useColorScheme } from 'react-native';

// Semantic color tokens — named by ROLE, not value, so the P7.5 native pass fills the
// dark half without touching call sites. Neutrals track iOS system grays (they read as
// native and adapt cleanly). Light values are real and QA'd; `dark` currently mirrors
// `light` (dark mode renders the light theme — "not yet supported", not broken). P7.5
// fills the dark half + QAs both modes; nothing else needs to change.
const light = {
  // Surfaces
  background: '#F2F2F7', // systemGroupedBackground — the feed's canvas behind cards
  surface: '#FFFFFF', // card / sheet
  surfaceSunken: '#E9E9EF', // skeleton base, inset fields

  // Text
  label: '#000000',
  labelSecondary: '#6C6C70', // secondaryLabel — venue, date, meta
  labelTertiary: '#B0B0B8', // tertiaryLabel — hints, placeholders

  // Lines
  separator: '#D1D1D6',

  // Brand — the single tint: primary actions, links, active chips
  accent: '#E8005A',
  accentSoft: '#FCE1EC', // low-alpha magenta for chip fills / selected states
  onAccent: '#FFFFFF',

  // Interest status — deliberately NOT the accent (a mark is a state, not an action)
  going: '#34C759', // system green
  maybe: '#FF9500', // system orange
  onStatus: '#FFFFFF',

  // Destructive actions (remove mark, unfriend, block) — system red, never the accent
  destructive: '#FF3B30',
};

type Palette = typeof light;

// P7.5: replace this with real dark values. Kept identical to `light` for now so the
// structure (and useColorScheme wiring) exists without unverified dark colors shipping.
const dark: Palette = { ...light };

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radii = {
  sm: 8,
  md: 12, // buttons
  lg: 14, // cards
  pill: 999,
} as const;

// iOS system font (San Francisco) by leaving fontFamily unset. Dynamic Type comes free
// via RN's default allowFontScaling. Custom brand display font is deferred to P7.5.
export const type = {
  title: { fontSize: 22, fontWeight: '700', lineHeight: 28 },
  headline: { fontSize: 17, fontWeight: '600', lineHeight: 22 },
  body: { fontSize: 15, fontWeight: '400', lineHeight: 20 },
  callout: { fontSize: 14, fontWeight: '500', lineHeight: 19 },
  caption: { fontSize: 12, fontWeight: '500', lineHeight: 16 },
} as const;

// Static light palette — safe for module-scope StyleSheet.create. Prefer useTheme()
// inside components so P7.5's dark values flow through automatically.
export const colors = light;

export function useTheme() {
  const scheme = useColorScheme();
  return {
    colors: scheme === 'dark' ? dark : light,
    spacing,
    radii,
    type,
  };
}
