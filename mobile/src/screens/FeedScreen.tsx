import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, RefreshControl,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { FeedEvent, getFeed, removeInterest, setInterest } from '../api/feed';

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

  const toggleInterest = async (event: FeedEvent, level: 'going' | 'maybe') => {
    try {
      if (event.my_interest === level) {
        await removeInterest(event.id);
        setEvents((prev) => prev.map((e) => e.id === event.id ? { ...e, my_interest: null } : e));
      } else {
        await setInterest(event.id, level);
        setEvents((prev) => prev.map((e) => e.id === event.id ? { ...e, my_interest: level } : e));
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
          <View style={styles.actions}>
            <TouchableOpacity
              style={[styles.interestBtn, item.my_interest === 'going' && styles.activeGoing]}
              onPress={() => toggleInterest(item, 'going')}
            >
              <Text style={[styles.interestText, item.my_interest === 'going' && styles.activeText]}>Going</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.interestBtn, item.my_interest === 'maybe' && styles.activeMaybe]}
              onPress={() => toggleInterest(item, 'maybe')}
            >
              <Text style={[styles.interestText, item.my_interest === 'maybe' && styles.activeText]}>Maybe</Text>
            </TouchableOpacity>
          </View>
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
  actions: { flexDirection: 'row', gap: 8, marginTop: 12 },
  interestBtn: {
    flex: 1, borderWidth: 1, borderColor: '#ddd',
    borderRadius: 8, padding: 8, alignItems: 'center',
  },
  activeGoing: { backgroundColor: '#00897B', borderColor: '#00897B' },
  activeMaybe: { backgroundColor: '#FB8C00', borderColor: '#FB8C00' },
  interestText: { fontSize: 14, color: '#444', fontWeight: '500' },
  activeText: { color: '#fff' },
});
