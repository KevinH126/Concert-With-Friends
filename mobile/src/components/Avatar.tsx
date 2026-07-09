import React from 'react';
import { Text, View } from 'react-native';
import { useTheme } from '../theme';

// Deterministic, muted avatar tints — same friend always gets the same color, so a row
// of avatars reads as distinct people. Chosen to sit calmly under the magenta accent.
const TINTS = ['#5E5CE6', '#30B0C7', '#34C759', '#FF9500', '#FF375F', '#AF52DE', '#A2845E'];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function tintFor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  return TINTS[hash % TINTS.length];
}

interface AvatarProps {
  name: string;
  size?: number;
  ring?: boolean; // white ring, for overlapping rows so faces stay separated
}

export function Avatar({ name, size = 28, ring }: AvatarProps) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: tintFor(name),
        alignItems: 'center',
        justifyContent: 'center',
        borderWidth: ring ? 2 : 0,
        borderColor: colors.surface,
      }}
    >
      <Text style={{ color: '#FFFFFF', fontSize: size * 0.4, fontWeight: '700' }}>
        {initials(name)}
      </Text>
    </View>
  );
}
