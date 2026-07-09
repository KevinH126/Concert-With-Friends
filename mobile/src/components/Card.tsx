import React from 'react';
import { StyleProp, View, ViewStyle } from 'react-native';
import { useTheme } from '../theme';

interface CardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  padded?: boolean; // false when a child (e.g. a hero image) must bleed to the edges
}

// The app's surface primitive: rounded, subtly raised, on the grouped background.
export function Card({ children, style, padded = true }: CardProps) {
  const { colors, radii, spacing } = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: colors.surface,
          borderRadius: radii.lg,
          padding: padded ? spacing.lg : 0,
          overflow: 'hidden', // clip the hero image to the card's rounded corners
          shadowColor: '#000',
          shadowOpacity: 0.06,
          shadowRadius: 8,
          shadowOffset: { width: 0, height: 2 },
          elevation: 2,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}
