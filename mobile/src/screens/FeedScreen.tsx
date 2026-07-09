import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, RefreshControl, Share,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { Image } from 'expo-image';
import { useFocusEffect } from '@react-navigation/native';
import {
  FeedEvent, FriendGoing, FriendPredicted, getFeed, removeInterest, setInterest,
} from '../api/feed';
import { EventSearchResult, searchEvents } from '../api/events';
import { Avatar, Card, Chip, Icon, IconName } from '../components';
import { radii, spacing, type as typeScale, useTheme } from '../theme';

function joinNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? '';
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// Avatars carry "who", so the summary is just the verb phrase — no emoji, no icon.
function goingSummary(fg: FriendGoing[]): string {
  const going = fg.filter((f) => f.level === 'going').map((f) => f.display_name);
  const maybe = fg.filter((f) => f.level === 'maybe').map((f) => f.display_name);
  const parts: string[] = [];
  if (going.length) parts.push(`${joinNames(going)} ${going.length > 1 ? 'are' : 'is'} going`);
  if (maybe.length) parts.push(`${joinNames(maybe)} might go`);
  return parts.join(' · ');
}

// Predictions name *why* (the strongest taste signal). The icon replaces the old emoji:
// a favorite-artist reason gets the star, everything else the sparkles.
function predictionParts(fp: FriendPredicted, artistName: string | null): { icon: IconName; text: string } {
  const who = fp.display_name;
  if (fp.reason_kind === 'favorite_artist' && artistName) {
    return { icon: 'favorite', text: `${artistName} is one of ${who}'s favorites` };
  }
  if (fp.reason_kind === 'artist' && artistName) {
    return { icon: 'prediction', text: `${who} is into ${artistName}` };
  }
  if (fp.reason_kind === 'genre' && fp.reason_genre) {
    return { icon: 'prediction', text: `Matches ${who}'s taste in ${fp.reason_genre}` };
  }
  return { icon: 'prediction', text: `${who} might be into this` };
}

function genreLabel(genre: string | null, subgenre: string | null): string | null {
  if (genre && subgenre && genre !== subgenre) return `${genre} · ${subgenre}`;
  return subgenre ?? genre ?? null;
}

function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

// Hero image, or a calm branded placeholder when TM gave us no image for the show.
function HeroImage({ uri }: { uri: string | null }) {
  const { colors } = useTheme();
  if (!uri) {
    return (
      <View style={[styles.hero, styles.heroFallback, { backgroundColor: colors.surfaceSunken }]}>
        <Icon name="music" size={32} color={colors.labelTertiary} />
      </View>
    );
  }
  return <Image source={uri} style={styles.hero} contentFit="cover" transition={200} />;
}

export default function FeedScreen() {
  const { colors } = useTheme();
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

  // Tap = shared interest; long-press = private. Tapping the active level clears it.
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

  // A single interest toggle (Going/Maybe). Active fills with the status color.
  const InterestToggle = ({
    label, level, active, isPrivate, onPress, onLongPress,
  }: {
    label: string;
    level: 'going' | 'maybe';
    active: boolean;
    isPrivate?: boolean;
    onPress: () => void;
    onLongPress?: () => void;
  }) => {
    const activeColor = level === 'going' ? colors.going : colors.maybe;
    return (
      <TouchableOpacity
        style={[
          styles.interestBtn,
          { borderColor: active ? activeColor : colors.separator },
          active && { backgroundColor: activeColor },
        ]}
        onPress={onPress}
        onLongPress={onLongPress}
        activeOpacity={0.7}
      >
        <Text style={[styles.interestText, { color: active ? colors.onStatus : colors.labelSecondary }]}>
          {label}
        </Text>
        {active && isPrivate && <Icon name="private" size={13} color={colors.onStatus} />}
      </TouchableOpacity>
    );
  };

  if (loading) {
    return <ActivityIndicator style={styles.center} size="large" color={colors.accent} />;
  }

  if (needsMetro) {
    return (
      <View style={[styles.container, styles.center, { backgroundColor: colors.background }]}>
        <Icon name="search" size={40} color={colors.labelTertiary} />
        <Text style={[styles.empty, { color: colors.label }]}>Set your home metro to see shows.</Text>
        <Text style={[styles.emptySub, { color: colors.labelSecondary }]}>
          Go to the Profile tab and enter your metro ID.
        </Text>
      </View>
    );
  }

  const searchBar = (
    <View style={[styles.searchField, { backgroundColor: colors.surface, borderColor: colors.separator }]}>
      <Icon name="search" size={17} color={colors.labelTertiary} />
      <TextInput
        style={[styles.searchInput, { color: colors.label }]}
        placeholder="Search shows, artists, venues…"
        placeholderTextColor={colors.labelTertiary}
        value={query}
        onChangeText={setQuery}
        autoCorrect={false}
        clearButtonMode="while-editing"
      />
    </View>
  );

  // Search-result card: same hero + core info, simpler actions (no private, no social).
  if (results !== null) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.searchWrap}>{searchBar}</View>
        {searching ? (
          <ActivityIndicator style={{ marginTop: spacing.xl }} color={colors.accent} />
        ) : (
          <FlatList
            data={results}
            keyExtractor={(r) => r.id}
            contentContainerStyle={styles.list}
            ListEmptyComponent={
              <Text style={[styles.emptySub, { color: colors.labelSecondary, textAlign: 'center', marginTop: spacing.xl }]}>
                No upcoming shows match "{query.trim()}".
              </Text>
            }
            renderItem={({ item }) => (
              <Card padded={false}>
                <HeroImage uri={item.image_url} />
                <View style={styles.cardBody}>
                  <Text style={[styles.eventName, { color: colors.label }]}>{item.name}</Text>
                  {item.artist_name && (
                    <Text style={[styles.meta, { color: colors.labelSecondary }]}>{item.artist_name}</Text>
                  )}
                  {item.venue_name && (
                    <Text style={[styles.meta, { color: colors.labelSecondary }]}>{item.venue_name}</Text>
                  )}
                  {item.starts_at && (
                    <Text style={[styles.date, { color: colors.accent }]}>{formatDate(item.starts_at)}</Text>
                  )}
                  {genreLabel(item.genre, null) && (
                    <View style={styles.chipRow}><Chip label={genreLabel(item.genre, null)!} /></View>
                  )}
                  <View style={styles.actions}>
                    <InterestToggle
                      label="Going" level="going" active={item.my_interest === 'going'}
                      onPress={() => toggleSearchInterest(item, 'going')}
                    />
                    <InterestToggle
                      label="Maybe" level="maybe" active={item.my_interest === 'maybe'}
                      onPress={() => toggleSearchInterest(item, 'maybe')}
                    />
                  </View>
                </View>
              </Card>
            )}
          />
        )}
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={styles.searchWrap}>{searchBar}</View>
      {events.length === 0 ? (
        <View style={[styles.center, { paddingBottom: 80 }]}>
          <Icon name="music" size={40} color={colors.labelTertiary} />
          <Text style={[styles.empty, { color: colors.label }]}>No upcoming shows match your taste.</Text>
          <Text style={[styles.emptySub, { color: colors.labelSecondary }]}>
            Add artists or genres in the Taste tab.
          </Text>
        </View>
      ) : (
        <FlatList
          data={events}
          keyExtractor={(e) => e.id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => {
            const summary = goingSummary(item.friends_going);
            return (
              <Card padded={false}>
                <HeroImage uri={item.image_url} />
                <View style={styles.cardBody}>
                  <Text style={[styles.eventName, { color: colors.label }]}>{item.name}</Text>

                  {/* Social headline — confirmed friends, elevated with faces. */}
                  {item.friends_going.length > 0 && (
                    <View style={styles.social}>
                      <View style={styles.avatarRow}>
                        {item.friends_going.slice(0, 4).map((f, i) => (
                          <View key={f.user_id} style={{ marginLeft: i === 0 ? 0 : -8 }}>
                            <Avatar name={f.display_name} size={26} ring />
                          </View>
                        ))}
                      </View>
                      <Text style={[styles.socialText, { color: colors.label }]} numberOfLines={2}>
                        {summary}
                      </Text>
                    </View>
                  )}

                  {item.artist_name && (
                    <Text style={[styles.meta, { color: colors.labelSecondary }]}>{item.artist_name}</Text>
                  )}
                  {item.venue_name && (
                    <Text style={[styles.meta, { color: colors.labelSecondary }]}>{item.venue_name}</Text>
                  )}
                  {item.starts_at && (
                    <Text style={[styles.date, { color: colors.accent }]}>{formatDate(item.starts_at)}</Text>
                  )}
                  {genreLabel(item.genre, item.subgenre) && (
                    <View style={styles.chipRow}><Chip label={genreLabel(item.genre, item.subgenre)!} /></View>
                  )}

                  {/* Predictions — quiet, avatar-less, reason-named. */}
                  {item.friends_predicted.map((fp) => {
                    const p = predictionParts(fp, item.artist_name);
                    return (
                      <View key={fp.user_id} style={styles.predicted}>
                        <Icon name={p.icon} size={13} color={colors.labelTertiary} />
                        <Text style={[styles.predictedText, { color: colors.labelSecondary }]}>{p.text}</Text>
                      </View>
                    );
                  })}

                  <View style={styles.actions}>
                    <InterestToggle
                      label="Going" level="going"
                      active={item.my_interest === 'going'}
                      isPrivate={item.my_interest_visibility === 'private'}
                      onPress={() => toggleInterest(item, 'going')}
                      onLongPress={() => toggleInterest(item, 'going', 'private')}
                    />
                    <InterestToggle
                      label="Maybe" level="maybe"
                      active={item.my_interest === 'maybe'}
                      isPrivate={item.my_interest_visibility === 'private'}
                      onPress={() => toggleInterest(item, 'maybe')}
                      onLongPress={() => toggleInterest(item, 'maybe', 'private')}
                    />
                  </View>

                  {item.friends_going.length > 0 && (
                    <TouchableOpacity
                      style={[styles.planBtn, { borderColor: colors.accent }]}
                      onPress={() => shareEvent(item)}
                      activeOpacity={0.7}
                    >
                      <Icon name="share" size={16} color={colors.accent} weight="semibold" />
                      <Text style={[styles.planText, { color: colors.accent }]}>Make a plan</Text>
                    </TouchableOpacity>
                  )}

                  <Text style={[styles.hint, { color: colors.labelTertiary }]}>
                    Long-press Going/Maybe to mark privately
                  </Text>
                </View>
              </Card>
            );
          }}
        />
      )}
    </View>
  );
}

// Layout/metrics only — all colors come from the theme at render time (so P7.5's dark
// values flow through without touching this sheet).
const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: spacing.sm },
  empty: { ...typeScale.headline, marginTop: spacing.sm },
  emptySub: { ...typeScale.body },
  searchWrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xs },
  searchField: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    borderWidth: 1, borderRadius: radii.md, paddingHorizontal: spacing.md, height: 40,
  },
  searchInput: { flex: 1, ...typeScale.body },
  list: { padding: spacing.lg, gap: spacing.lg },
  hero: { width: '100%', aspectRatio: 16 / 9 },
  heroFallback: { alignItems: 'center', justifyContent: 'center' },
  cardBody: { padding: spacing.lg, gap: spacing.xs },
  eventName: { ...typeScale.title },
  meta: { ...typeScale.body },
  date: { ...typeScale.callout, marginTop: spacing.xs },
  chipRow: { marginTop: spacing.xs, marginBottom: spacing.xs },
  social: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    marginTop: spacing.xs, marginBottom: spacing.xs,
  },
  avatarRow: { flexDirection: 'row' },
  socialText: { ...typeScale.headline, flex: 1 },
  predicted: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
  predictedText: { ...typeScale.callout, flex: 1 },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  interestBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.xs,
    borderWidth: 1, borderRadius: radii.md, paddingVertical: spacing.md,
  },
  interestText: { ...typeScale.headline },
  planBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    borderWidth: 1, borderRadius: radii.md, paddingVertical: spacing.md, marginTop: spacing.sm,
  },
  planText: { ...typeScale.headline },
  hint: { ...typeScale.caption, textAlign: 'center', marginTop: spacing.sm },
});
