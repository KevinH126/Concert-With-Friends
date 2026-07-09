import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { useTheme } from '../theme';
import { Icon } from './Icon';

interface ChipProps {
  label: string;
  // 'display' = static tag (e.g. a genre on a card). 'selectable' = toggles; `selected`
  // fills it with the accent. Provide onRemove to show a tap-to-remove ✕ (taste chips).
  variant?: 'display' | 'selectable';
  selected?: boolean;
  onPress?: () => void;
  onRemove?: () => void;
}

export function Chip({ label, variant = 'display', selected, onPress, onRemove }: ChipProps) {
  const { colors, radii, spacing, type } = useTheme();
  const active = variant === 'selectable' && selected;

  const body = (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: spacing.xs,
        alignSelf: 'flex-start',
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.xs + 2,
        borderRadius: radii.pill,
        backgroundColor: active ? colors.accent : colors.accentSoft,
      }}
    >
      <Text style={{ ...type.caption, color: active ? colors.onAccent : colors.accent }}>
        {label}
      </Text>
      {onRemove && (
        <TouchableOpacity onPress={onRemove} hitSlop={8}>
          <Icon name="close" size={13} color={active ? colors.onAccent : colors.accent} />
        </TouchableOpacity>
      )}
    </View>
  );

  if (onPress) {
    return (
      <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
        {body}
      </TouchableOpacity>
    );
  }
  return body;
}
