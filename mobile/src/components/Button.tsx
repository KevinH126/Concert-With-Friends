import React from 'react';
import {
  ActivityIndicator, StyleProp, Text, TouchableOpacity, View, ViewStyle,
} from 'react-native';
import { useTheme } from '../theme';
import { Icon, IconName } from './Icon';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary';
  icon?: IconName;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}

// primary = magenta fill (the app's one call-to-action look); secondary = outline.
export function Button({
  title, onPress, variant = 'primary', icon, disabled, loading, style,
}: ButtonProps) {
  const { colors, radii, spacing, type } = useTheme();
  const isPrimary = variant === 'primary';
  const fg = isPrimary ? colors.onAccent : colors.accent;
  const inactive = disabled || loading;

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={inactive}
      activeOpacity={0.7}
      style={[
        {
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: spacing.sm,
          paddingVertical: spacing.md,
          paddingHorizontal: spacing.lg,
          borderRadius: radii.md,
          backgroundColor: isPrimary ? colors.accent : 'transparent',
          borderWidth: isPrimary ? 0 : 1,
          borderColor: colors.accent,
          opacity: inactive ? 0.45 : 1,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
          {icon && <Icon name={icon} size={18} color={fg} weight="semibold" />}
          <Text style={{ ...type.headline, color: fg }}>{title}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}
