import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import { FriendProfile, blockUser, getFriendProfile, unfriend } from '../api/friends';

export default function FriendProfileScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { userId } = route.params as { userId: string };
  const [profile, setProfile] = useState<FriendProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setProfile(await getFriendProfile(userId));
    } catch {
      Alert.alert('Error', 'Could not load this profile');
      navigation.goBack();
    }
  }, [userId, navigation]);

  useFocusEffect(
    useCallback(() => {
      load().finally(() => setLoading(false));
    }, [load]),
  );

  const confirmUnfriend = () => {
    Alert.alert('Unfriend', `Remove ${profile?.display_name} from your friends?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Unfriend',
        style: 'destructive',
        onPress: async () => {
          await unfriend(userId);
          navigation.goBack();
        },
      },
    ]);
  };

  const confirmBlock = () => {
    Alert.alert(
      'Block',
      `Block ${profile?.display_name}? You won't see each other in the app at all. They won't be notified.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Block',
          style: 'destructive',
          onPress: async () => {
            await blockUser(userId);
            navigation.goBack();
          },
        },
      ],
    );
  };

  if (loading || !profile) {
    return <ActivityIndicator style={styles.center} size="large" color="#6200EE" />;
  }

  const favorites = profile.artists.filter((a) => a.weight >= 2);
  const liked = profile.artists.filter((a) => a.weight < 2);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.name}>{profile.display_name}</Text>
      {profile.username && <Text style={styles.username}>@{profile.username}</Text>}
      {profile.home_metro_id && <Text style={styles.meta}>Metro: {profile.home_metro_id}</Text>}

      <Text style={styles.section}>Going / interested</Text>
      {profile.interests.length === 0 ? (
        <Text style={styles.empty}>No upcoming shows marked yet.</Text>
      ) : (
        profile.interests.map((i) => (
          <View key={i.event_id} style={styles.card}>
            <Text style={styles.eventName}>{i.event_name}</Text>
            {i.venue_name && <Text style={styles.meta}>{i.venue_name}</Text>}
            {i.starts_at && (
              <Text style={styles.date}>
                {new Date(i.starts_at).toLocaleDateString(undefined, {
                  weekday: 'short', month: 'short', day: 'numeric',
                })}
              </Text>
            )}
            <Text style={[styles.badge, i.level === 'going' ? styles.badgeGoing : styles.badgeMaybe]}>
              {i.level === 'going' ? 'Going' : 'Maybe'}
            </Text>
          </View>
        ))
      )}

      <Text style={styles.section}>Favorite artists</Text>
      {favorites.length === 0 ? (
        <Text style={styles.empty}>None yet.</Text>
      ) : (
        <View style={styles.chips}>
          {favorites.map((a) => <Text key={a.name} style={[styles.chip, styles.chipFav]}>★ {a.name}</Text>)}
        </View>
      )}

      <Text style={styles.section}>Liked artists</Text>
      {liked.length === 0 ? (
        <Text style={styles.empty}>None yet.</Text>
      ) : (
        <View style={styles.chips}>
          {liked.map((a) => <Text key={a.name} style={styles.chip}>{a.name}</Text>)}
        </View>
      )}

      <Text style={styles.section}>Genres</Text>
      {profile.genres.length === 0 ? (
        <Text style={styles.empty}>None yet.</Text>
      ) : (
        <View style={styles.chips}>
          {profile.genres.map((g) => <Text key={g} style={styles.chip}>{g}</Text>)}
        </View>
      )}

      <View style={styles.dangerRow}>
        <TouchableOpacity style={styles.outlineBtn} onPress={confirmUnfriend}>
          <Text style={styles.outlineBtnText}>Unfriend</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.dangerBtn} onPress={confirmBlock}>
          <Text style={styles.dangerBtnText}>Block</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  container: { padding: 16 },
  name: { fontSize: 24, fontWeight: '700' },
  username: { fontSize: 15, color: '#888', marginBottom: 4 },
  meta: { fontSize: 14, color: '#555' },
  section: { fontSize: 13, fontWeight: '700', color: '#888', textTransform: 'uppercase', marginTop: 20, marginBottom: 8 },
  empty: { color: '#888', fontSize: 14 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 12, marginBottom: 8 },
  eventName: { fontSize: 16, fontWeight: '600' },
  date: { fontSize: 13, color: '#6200EE', marginTop: 2 },
  badge: {
    alignSelf: 'flex-start', marginTop: 6, fontSize: 12, fontWeight: '600',
    color: '#fff', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10,
  },
  badgeGoing: { backgroundColor: '#00897B' },
  badgeMaybe: { backgroundColor: '#FB8C00' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    backgroundColor: '#f0e6ff', color: '#6200EE', fontSize: 13,
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, overflow: 'hidden',
  },
  chipFav: { backgroundColor: '#6200EE', color: '#fff' },
  dangerRow: { flexDirection: 'row', gap: 8, marginTop: 32, marginBottom: 24 },
  outlineBtn: {
    flex: 1, borderWidth: 1, borderColor: '#bbb', borderRadius: 8,
    padding: 12, alignItems: 'center',
  },
  outlineBtnText: { color: '#666', fontWeight: '600' },
  dangerBtn: {
    flex: 1, backgroundColor: '#C62828', borderRadius: 8,
    padding: 12, alignItems: 'center',
  },
  dangerBtnText: { color: '#fff', fontWeight: '600' },
});
