import React from 'react';
import { Platform } from 'react-native';
import { SymbolView, SymbolWeight, SFSymbol } from 'expo-symbols';
import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { colors } from '../theme';

// Semantic icon names — call sites say what they mean, this maps to the platform glyph.
// iOS renders the SF Symbol; Android (a few friends) falls back to the Material equivalent.
type MaterialName = React.ComponentProps<typeof MaterialIcons>['name'];

const MAP: Record<string, { sf: SFSymbol; material: MaterialName }> = {
  friends: { sf: 'person.2.fill', material: 'group' },
  prediction: { sf: 'sparkles', material: 'auto-awesome' },
  favorite: { sf: 'star.fill', material: 'star' },
  private: { sf: 'lock.fill', material: 'lock' },
  share: { sf: 'square.and.arrow.up', material: 'ios-share' },
  search: { sf: 'magnifyingglass', material: 'search' },
  close: { sf: 'xmark', material: 'close' },
  chevronRight: { sf: 'chevron.right', material: 'chevron-right' },
  chevronDown: { sf: 'chevron.down', material: 'keyboard-arrow-down' },
  add: { sf: 'plus', material: 'add' },
  check: { sf: 'checkmark', material: 'check' },
  music: { sf: 'music.note', material: 'music-note' },
};

export type IconName = keyof typeof MAP;

interface IconProps {
  name: IconName;
  size?: number;
  color?: string;
  weight?: SymbolWeight; // iOS only; Android ignores
}

export function Icon({ name, size = 20, color = colors.label, weight = 'regular' }: IconProps) {
  const glyph = MAP[name];
  if (Platform.OS === 'ios') {
    return (
      <SymbolView
        name={glyph.sf}
        size={size}
        tintColor={color}
        weight={weight}
        resizeMode="scaleAspectFit"
      />
    );
  }
  return <MaterialIcons name={glyph.material} size={size} color={color} />;
}
