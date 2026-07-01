import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, RefreshControl,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { FeedEvent, FriendGoing, getFeed, removeInterest, setInterest } from '../api/feed';

function joinNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? '';
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

function friendsGoingText(fg: FriendGoing[]): string {
  const going = fg.filter((f) => f.level === 'going').map((f) => f.display_name);
  const maybe = fg.filter((f) => f.level === 'maybe').map((f) => f.display_name);
  const parts: string[] = [];
  if (going.length) parts.push(`${joinNames(going)} ${going.length > 1 ? 'are' : 'is'} going`);
  if (maybe.length) parts.push(`${joinNames(maybe)} might go`);
  return `👥 ${parts.join(' · ')}`;
}

export default function FeedScreen() {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [needsMetro, setNeedsMetro] = useState(false);

  const load = useCallback(async () => {
    try {
      setNeedsMetro(false);
      const data = await getFeed();
      setEvents(data);
    } catch (e: any) {
      const detail: string = e?.response?.data?.detail ?? '';
      if (e?.response?.status === 400 && detail.includes('home_metro_id')) {
        setNeedsMetro(true);
      } else {
        Alert.alert('Error', detail || 'Could not load feed');
      }
    }
  }, []);

  // Reload whenever the tab regains focus (taste/metro may have changed on another
  // tab). The screen stays mounted in the tab navigator, so a mount-only effect would
  // never refetch. Existing events stay visible during the refetch — no spinner flicker.
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

  // Tap = shared interest; long-press = private (feeds your own feed/notifications
  // but is hidden from friends). Tapping the same active level clears it.
  const toggleInterest = async (
    event: FeedEvent,
    level: 'going' | 'maybe',
    visibility: 'shared' | 'private' = 'shared',
  ) => {
    try {
      if (event.my_interest === level && event.my_interest_visibility === visibility) {
        await removeInterest(event.id);
        setEvents((prev) => prev.map((e) =>
          e.id === event.id ? { ...e, my_interest: null, my_interest_visibility: null } : e));
      } else {
        await setInterest(event.id, level, visibility);
        setEvents((prev) => prev.map((e) =>
          e.id === event.id ? { ...e, my_interest: level, my_interest_visibility: visibility } : e));
      }
    } catch {
      Alert.alert('Error', 'Could not update interest');
    }
  };

  if (loading) {
    return <ActivityIndicator style={styles.center} size="large" color="#6200EE" />;
  }

  if (needsMetro) {
    return (
      <View style={styles.center}>
        <Text style={styles.empty}>Set your home metro to see shows.</Text>
        <Text style={styles.emptySub}>Go to the Profile tab and enter your metro ID.</Text>
      </View>
    );
  }

  if (events.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.empty}>No upcoming shows match your taste.</Text>
        <Text style={styles.emptySub}>Add artists or genres in the Taste tab.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={events}
      keyExtractor={(e) => e.id}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      contentContainerStyle={styles.list}
      renderItem={({ item }) => (
        <View style={styles.card}>
          <Text style={styles.eventName}>{item.name}</Text>
          {item.artist_name && <Text style={styles.meta}>{item.artist_name}</Text>}
          {item.venue_name && <Text style={styles.meta}>{item.venue_name}</Text>}
          {item.starts_at && (
            <Text style={styles.date}>{new Date(item.starts_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</Text>
          )}
          {item.genre && <Text style={styles.genre}>{item.genre}</Text>}
          {item.friends_going.length > 0 && (
            <Text style={styles.friendsStrip}>{friendsGoingText(item.friends_going)}</Text>
          )}
          <View style={styles.actions}>
            <TouchableOpacity
              style={[styles.interestBtn, item.my_interest === 'going' && styles.activeGoing]}
              onPress={() => toggleInterest(item, 'going')}
              onLongPress={() => toggleInterest(item, 'going', 'private')}
            >
              <Text style={[styles.interestText, item.my_interest === 'going' && styles.activeText]}>
                Going{item.my_interest === 'going' && item.my_interest_visibility === 'private' ? ' 🔒' : ''}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.interestBtn, item.my_interest === 'maybe' && styles.activeMaybe]}
              onPress={() => toggleInterest(item, 'maybe')}
              onLongPress={() => toggleInterest(item, 'maybe', 'private')}
            >
              <Text style={[styles.interestText, item.my_interest === 'maybe' && styles.activeText]}>
                Maybe{item.my_interest === 'maybe' && item.my_interest_visibility === 'private' ? ' 🔒' : ''}
              </Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.hint}>Long-press to mark privately (hidden from friends)</Text>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  empty: { fontSize: 16, color: '#444', marginBottom: 8 },
  emptySub: { fontSize: 14, color: '#888' },
  list: { padding: 16, gap: 12 },
  card: {
    backgroundColor: '#fff', borderRadius: 12, padding: 16,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 8, elevation: 2,
  },
  eventName: { fontSize: 17, fontWeight: '600', marginBottom: 4 },
  meta: { fontSize: 14, color: '#555' },
  date: { fontSize: 13, color: '#6200EE', marginTop: 4 },
  genre: {
    alignSelf: 'flex-start', marginTop: 6,
    backgroundColor: '#f0e6ff', color: '#6200EE',
    fontSize: 12, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10,
  },
  friendsStrip: { fontSize: 13, color: '#00695C', marginTop: 8, fontWeight: '500' },
  actions: { flexDirection: 'row', gap: 8, marginTop: 12 },
  hint: { fontSize: 11, color: '#aaa', marginTop: 6, textAlign: 'center' },
  interestBtn: {
    flex: 1, borderWidth: 1, borderColor: '#ddd',
    borderRadius: 8, padding: 8, alignItems: 'center',
  },
  activeGoing: { backgroundColor: '#00897B', borderColor: '#00897B' },
  activeMaybe: { backgroundColor: '#FB8C00', borderColor: '#FB8C00' },
  interestText: { fontSize: 14, color: '#444', fontWeight: '500' },
  activeText: { color: '#fff' },
});
