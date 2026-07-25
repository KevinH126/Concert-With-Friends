import React, { useCallback, useState } from 'react';
import {
  Alert, RefreshControl, SectionList,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { MyInterest, getMyInterests, removeInterest } from '../api/feed';
import { Card, Icon, RowCardSkeleton } from '../components';
import { radii, spacing, type as typeScale, useTheme } from '../theme';

// The system of record for your marks. The feed only shows upcoming events, so
// without this screen a mark on a past show is invisible — yet still teaches
// the scorer your taste until you remove it here.
export default function MyShowsScreen() {
  const { colors } = useTheme();
  const [interests, setInterests] = useState<MyInterest[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setInterests(await getMyInterests());
    } catch {
      Alert.alert('Error', 'Could not load your shows');
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load().finally(() => setLoading(false));
    }, [load]),
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const unmark = (item: MyInterest) => {
    Alert.alert(
      'Remove mark?',
      `You'll no longer be ${item.level === 'going' ? 'going to' : 'maybe going to'} "${item.name}". This also stops it counting toward your taste.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            try {
              await removeInterest(item.id);
              setInterests((prev) => prev.filter((i) => i.id !== item.id));
            } catch {
              Alert.alert('Error', 'Could not remove mark');
            }
          },
        },
      ],
    );
  };

  if (loading) {
    return (
      <View style={[styles.list, { flex: 1, backgroundColor: colors.background }]}>
        <RowCardSkeleton />
        <RowCardSkeleton />
        <RowCardSkeleton />
      </View>
    );
  }

  const upcoming = interests.filter((i) => !i.is_past);
  const past = interests.filter((i) => i.is_past);
  const sections = [
    ...(upcoming.length ? [{ title: 'Upcoming', data: upcoming }] : []),
    ...(past.length ? [{ title: 'Past', data: past }] : []),
  ];

  if (sections.length === 0) {
    return (
      <View style={[styles.center, { backgroundColor: colors.background }]}>
        <Icon name="favorite" size={40} color={colors.labelTertiary} />
        <Text style={[styles.empty, { color: colors.label }]}>No marked shows yet.</Text>
        <Text style={[styles.emptySub, { color: colors.labelSecondary }]}>
          Mark shows as Going or Maybe from the Feed.
        </Text>
      </View>
    );
  }

  return (
    <SectionList
      style={{ backgroundColor: colors.background }}
      sections={sections}
      keyExtractor={(i) => i.id}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      contentContainerStyle={styles.list}
      renderSectionHeader={({ section }) => (
        <Text style={[styles.sectionHeader, { color: colors.labelSecondary }]}>{section.title}</Text>
      )}
      renderItem={({ item }) => {
        const statusColor = item.level === 'going' ? colors.going : colors.maybe;
        return (
          <Card style={[styles.card, item.is_past && styles.pastCard]}>
            <View style={styles.cardBody}>
              <Text style={[styles.eventName, { color: colors.label }]}>{item.name}</Text>
              {item.venue_name && <Text style={[styles.meta, { color: colors.labelSecondary }]}>{item.venue_name}</Text>}
              {item.starts_at && (
                <Text style={[styles.date, { color: colors.accent }]}>
                  {new Date(item.starts_at).toLocaleDateString(undefined, {
                    weekday: 'short', month: 'short', day: 'numeric',
                  })}
                </Text>
              )}
              <View style={styles.badgeRow}>
                <View style={[styles.badge, { backgroundColor: statusColor }]}>
                  <Text style={[styles.badgeText, { color: colors.onStatus }]}>
                    {item.level === 'going' ? 'Going' : 'Maybe'}
                  </Text>
                </View>
                {item.visibility === 'private' && (
                  <View style={styles.privateTag}>
                    <Icon name="private" size={12} color={colors.labelSecondary} />
                    <Text style={[styles.privateText, { color: colors.labelSecondary }]}>private</Text>
                  </View>
                )}
              </View>
            </View>
            <TouchableOpacity
              style={[styles.removeBtn, { borderColor: colors.destructive }]}
              onPress={() => unmark(item)}
              hitSlop={8}
            >
              <Text style={[styles.removeText, { color: colors.destructive }]}>Remove</Text>
            </TouchableOpacity>
          </Card>
        );
      }}
      stickySectionHeadersEnabled={false}
    />
  );
}

// Layout/metrics only — colors come from the theme at render time.
const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: spacing.sm },
  empty: { ...typeScale.headline, marginTop: spacing.sm },
  emptySub: { ...typeScale.body },
  list: { padding: spacing.lg, gap: spacing.md },
  sectionHeader: { ...typeScale.callout, fontWeight: '700', marginTop: spacing.sm },
  card: { flexDirection: 'row', alignItems: 'center' },
  pastCard: { opacity: 0.6 },
  cardBody: { flex: 1, gap: 2 },
  eventName: { ...typeScale.headline },
  meta: { ...typeScale.callout },
  date: { ...typeScale.caption, marginTop: 2 },
  badgeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm },
  badge: {
    alignSelf: 'flex-start', borderRadius: radii.pill,
    paddingHorizontal: spacing.sm, paddingVertical: 2,
  },
  badgeText: { ...typeScale.caption, fontWeight: '700' },
  privateTag: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  privateText: { ...typeScale.caption },
  removeBtn: {
    borderWidth: 1, borderRadius: radii.sm,
    paddingVertical: spacing.xs + 2, paddingHorizontal: spacing.md, marginLeft: spacing.md,
  },
  removeText: { ...typeScale.caption, fontWeight: '600' },
});
