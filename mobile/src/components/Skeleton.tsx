import React, { useEffect, useRef } from 'react';
import { Animated, DimensionValue, StyleProp, View, ViewStyle } from 'react-native';
import { radii, spacing, useTheme } from '../theme';
import { Card } from './Card';

// A single rounded placeholder block that gently pulses. All loading skeletons are
// built from these so the "loading" look is one system, tinted from the theme. Pass
// `aspectRatio` (e.g. the 16:9 hero) instead of `height` when the height must track width.
export function Skeleton({ width, height = 14, aspectRatio, radius = radii.sm, style }: {
  width?: DimensionValue;
  height?: number;
  aspectRatio?: number;
  radius?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useTheme();
  const pulse = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.4, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  return (
    <Animated.View
      style={[
        {
          width: width ?? '100%',
          ...(aspectRatio ? { aspectRatio } : { height }),
          borderRadius: radius,
          backgroundColor: colors.surfaceSunken,
          opacity: pulse,
        },
        style,
      ]}
    />
  );
}

// A feed-card-shaped skeleton: hero block + a title and two meta lines.
export function FeedCardSkeleton() {
  return (
    <Card padded={false}>
      <Skeleton radius={0} aspectRatio={16 / 9} />
      <View style={{ padding: spacing.lg, gap: spacing.sm }}>
        <Skeleton width="70%" height={20} />
        <Skeleton width="50%" />
        <Skeleton width="40%" />
      </View>
    </Card>
  );
}

// A compact row-card skeleton for My Shows / list screens.
export function RowCardSkeleton() {
  return (
    <Card style={{ gap: spacing.sm }}>
      <Skeleton width="65%" height={16} />
      <Skeleton width="45%" />
      <Skeleton width={70} height={20} radius={radii.pill} />
    </Card>
  );
}
