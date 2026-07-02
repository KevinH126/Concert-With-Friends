import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, RefreshControl, Share,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import {
  FeedEvent, FriendGoing, FriendPredicted, getFeed, removeInterest, setInterest,
} from '../api/feed';
import { EventSearchResult, searchEvents } from '../api/events';

function joinNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? '';
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// One strip, ordered marked-going > marked-maybe > predicted. The two prediction
// buckets are wording only — no scores or meters, per the locked P3 decision.
function friendsGoingText(fg: FriendGoing[]): string {
  const going = fg.filter((f) => f.level === 'going').map((f) => f.display_name);
  const maybe = fg.filter((f) => f.level === 'maybe').map((f) => f.display_name);
  const parts: string[] = [];
  if (going.length) parts.push(`${joinNames(going)} ${going.length > 1 ? 'are' : 'is'} going`);
  if (maybe.length) parts.push(`${joinNames(maybe)} might go`);
  return `👥 ${parts.join(' · ')}`;
}

function predictedText(fp: FriendPredicted[]): string {
  const probably = fp.filter((f) => f.bucket === 'probably').map((f) => f.display_name);
  const might = fp.filter((f) => f.bucket === 'might').map((f) => f.display_name);
  const parts: string[] = [];
  if (probably.length) parts.push(`${joinNames(probably)} would probably go`);
  if (might.length) parts.push(`${joinNames(might)} might be into this`);
  return `✨ ${parts.join(' · ')}`;
}

function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export default function FeedScreen() {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [needsMetro, setNeedsMetro] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<EventSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Debounced search over the cached metro events; <2 chars falls back to the feed.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (q.length < 2) {
      setResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        setResults(await searchEvents(q));
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

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

  // Search results only know the level (not visibility); tap toggles shared interest.
  const toggleSearchInterest = async (result: EventSearchResult, level: 'going' | 'maybe') => {
    try {
      if (result.my_interest === level) {
        await removeInterest(result.id);
        setResults((prev) => prev?.map((r) =>
          r.id === result.id ? { ...r, my_interest: null } : r) ?? null);
      } else {
        await setInterest(result.id, level, 'shared');
        setResults((prev) => prev?.map((r) =>
          r.id === result.id ? { ...r, my_interest: level } : r) ?? null);
      }
    } catch {
      Alert.alert('Error', 'Could not update interest');
    }
  };

  // Compose-sheet hand-off: ≥1 friend with shared MARKED interest is a plan.
  // In P7 this button points inward to in-app chat instead.
  const shareEvent = async (event: FeedEvent) => {
    const bits = [event.name, event.venue_name, formatDate(event.starts_at)]
      .filter(Boolean)
      .join(' — ');
    const message = event.url ? `${bits}\n${event.url}` : bits;
    try {
      await Share.share({ message });
    } catch {
      // user dismissed the sheet — nothing to do
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

  const searchBar = (
    <TextInput
      style={styles.searchInput}
      placeholder="Search shows, artists, venues…"
      value={query}
      onChangeText={setQuery}
      autoCorrect={false}
      clearButtonMode="while-editing"
    />
  );

  if (results !== null) {
    return (
      <View style={styles.container}>
        <View style={styles.searchWrap}>{searchBar}</View>
        {searching ? (
          <ActivityIndicator style={{ marginTop: 24 }} color="#6200EE" />
        ) : (
          <FlatList
            data={results}
            keyExtractor={(r) => r.id}
            contentContainerStyle={styles.list}
            ListEmptyComponent={
              <Text style={[styles.emptySub, { textAlign: 'center', marginTop: 24 }]}>
                No upcoming shows match "{query.trim()}".
              </Text>
            }
            renderItem={({ item }) => (
              <View style={styles.card}>
                <Text style={styles.eventName}>{item.name}</Text>
                {item.artist_name && <Text style={styles.meta}>{item.artist_name}</Text>}
                {item.venue_name && <Text style={styles.meta}>{item.venue_name}</Text>}
                {item.starts_at && <Text style={styles.date}>{formatDate(item.starts_at)}</Text>}
                <View style={styles.actions}>
                  <TouchableOpacity
                    style={[styles.interestBtn, item.my_interest === 'going' && styles.activeGoing]}
                    onPress={() => toggleSearchInterest(item, 'going')}
                  >
                    <Text style={[styles.interestText, item.my_interest === 'going' && styles.activeText]}>
                      Going
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.interestBtn, item.my_interest === 'maybe' && styles.activeMaybe]}
                    onPress={() => toggleSearchInterest(item, 'maybe')}
                  >
                    <Text style={[styles.interestText, item.my_interest === 'maybe' && styles.activeText]}>
                      Maybe
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          />
        )}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.searchWrap}>{searchBar}</View>
      {events.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.empty}>No upcoming shows match your taste.</Text>
          <Text style={styles.emptySub}>Add artists or genres in the Taste tab.</Text>
        </View>
      ) : (
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
              {item.starts_at && <Text style={styles.date}>{formatDate(item.starts_at)}</Text>}
              {item.genre && <Text style={styles.genre}>{item.genre}</Text>}
              {item.friends_going.length > 0 && (
                <Text style={styles.friendsStrip}>{friendsGoingText(item.friends_going)}</Text>
              )}
              {item.friends_predicted.length > 0 && (
                <Text style={styles.predictedStrip}>{predictedText(item.friends_predicted)}</Text>
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
                {item.friends_going.length > 0 && (
                  <TouchableOpacity style={styles.shareBtn} onPress={() => shareEvent(item)}>
                    <Text style={styles.shareText}>Make a plan ↗</Text>
                  </TouchableOpacity>
                )}
              </View>
              <Text style={styles.hint}>Long-press to mark privately (hidden from friends)</Text>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  empty: { fontSize: 16, color: '#444', marginBottom: 8 },
  emptySub: { fontSize: 14, color: '#888' },
  searchWrap: { paddingHorizontal: 16, paddingTop: 12 },
  searchInput: {
    borderWidth: 1, borderColor: '#ddd', backgroundColor: '#fff',
    borderRadius: 10, padding: 10, fontSize: 15,
  },
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
  predictedStrip: { fontSize: 13, color: '#7B1FA2', marginTop: 4, fontWeight: '500' },
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
  shareBtn: {
    flex: 1, borderWidth: 1, borderColor: '#6200EE',
    borderRadius: 8, padding: 8, alignItems: 'center',
  },
  shareText: { fontSize: 14, color: '#6200EE', fontWeight: '600' },
});
