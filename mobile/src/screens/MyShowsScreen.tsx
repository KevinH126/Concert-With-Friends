import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, RefreshControl, SectionList,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { MyInterest, getMyInterests, removeInterest } from '../api/feed';

// The system of record for your marks. The feed only shows upcoming events, so
// without this screen a mark on a past show is invisible — yet still teaches
// the scorer your taste until you remove it here.
export default function MyShowsScreen() {
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
    return <ActivityIndicator style={styles.center} size="large" color="#6200EE" />;
  }

  const upcoming = interests.filter((i) => !i.is_past);
  const past = interests.filter((i) => i.is_past);
  const sections = [
    ...(upcoming.length ? [{ title: 'Upcoming', data: upcoming }] : []),
    ...(past.length ? [{ title: 'Past', data: past }] : []),
  ];

  if (sections.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.empty}>No marked shows yet.</Text>
        <Text style={styles.emptySub}>Mark shows as Going or Maybe from the Feed.</Text>
      </View>
    );
  }

  return (
    <SectionList
      sections={sections}
      keyExtractor={(i) => i.id}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      contentContainerStyle={styles.list}
      renderSectionHeader={({ section }) => (
        <Text style={styles.sectionHeader}>{section.title}</Text>
      )}
      renderItem={({ item }) => (
        <View style={[styles.card, item.is_past && styles.pastCard]}>
          <View style={styles.cardBody}>
            <Text style={styles.eventName}>{item.name}</Text>
            {item.venue_name && <Text style={styles.meta}>{item.venue_name}</Text>}
            {item.starts_at && (
              <Text style={styles.date}>
                {new Date(item.starts_at).toLocaleDateString(undefined, {
                  weekday: 'short', month: 'short', day: 'numeric',
                })}
              </Text>
            )}
            <Text style={[styles.badge, item.level === 'going' ? styles.goingBadge : styles.maybeBadge]}>
              {item.level === 'going' ? 'Going' : 'Maybe'}
              {item.visibility === 'private' ? ' 🔒 private' : ''}
            </Text>
          </View>
          <TouchableOpacity style={styles.removeBtn} onPress={() => unmark(item)} hitSlop={8}>
            <Text style={styles.removeText}>Remove</Text>
          </TouchableOpacity>
        </View>
      )}
      stickySectionHeadersEnabled={false}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  empty: { fontSize: 16, color: '#444', marginBottom: 8 },
  emptySub: { fontSize: 14, color: '#888' },
  list: { padding: 16 },
  sectionHeader: { fontSize: 15, fontWeight: '700', color: '#666', marginTop: 8, marginBottom: 8 },
  card: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#fff', borderRadius: 12, padding: 14, marginBottom: 10,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 8, elevation: 2,
  },
  pastCard: { opacity: 0.6 },
  cardBody: { flex: 1 },
  eventName: { fontSize: 15, fontWeight: '600', marginBottom: 2 },
  meta: { fontSize: 13, color: '#555' },
  date: { fontSize: 12, color: '#6200EE', marginTop: 2 },
  badge: { alignSelf: 'flex-start', fontSize: 12, fontWeight: '600', marginTop: 6 },
  goingBadge: { color: '#00897B' },
  maybeBadge: { color: '#FB8C00' },
  removeBtn: {
    borderWidth: 1, borderColor: '#E53935', borderRadius: 8,
    paddingVertical: 6, paddingHorizontal: 10, marginLeft: 10,
  },
  removeText: { color: '#E53935', fontSize: 13, fontWeight: '600' },
});
