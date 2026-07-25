import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import { FriendProfile, blockUser, getFriendProfile, unfriend } from '../api/friends';
import { Avatar, Card, Chip, Icon } from '../components';
import { radii, spacing, type as typeScale, useTheme } from '../theme';

export default function FriendProfileScreen() {
  const { colors } = useTheme();
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
    return (
      <View style={[styles.center, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  const favorites = profile.artists.filter((a) => a.weight >= 2);
  const liked = profile.artists.filter((a) => a.weight < 2);

  return (
    <ScrollView
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={styles.container}
    >
      <View style={styles.header}>
        <Avatar name={profile.display_name} size={64} />
        <View style={styles.headerText}>
          <Text style={[styles.name, { color: colors.label }]}>{profile.display_name}</Text>
          {profile.username && <Text style={[styles.username, { color: colors.labelSecondary }]}>@{profile.username}</Text>}
          {profile.home_metro_id && <Text style={[styles.meta, { color: colors.labelSecondary }]}>Metro: {profile.home_metro_id}</Text>}
        </View>
      </View>

      <Text style={[styles.section, { color: colors.labelSecondary }]}>Going / interested</Text>
      {profile.interests.length === 0 ? (
        <Text style={[styles.empty, { color: colors.labelSecondary }]}>No upcoming shows marked yet.</Text>
      ) : (
        profile.interests.map((i) => {
          const statusColor = i.level === 'going' ? colors.going : colors.maybe;
          return (
            <Card key={i.event_id} style={styles.card}>
              <Text style={[styles.eventName, { color: colors.label }]}>{i.event_name}</Text>
              {i.venue_name && <Text style={[styles.meta, { color: colors.labelSecondary }]}>{i.venue_name}</Text>}
              {i.starts_at && (
                <Text style={[styles.date, { color: colors.accent }]}>
                  {new Date(i.starts_at).toLocaleDateString(undefined, {
                    weekday: 'short', month: 'short', day: 'numeric',
                  })}
                </Text>
              )}
              <View style={[styles.badge, { backgroundColor: statusColor }]}>
                <Text style={[styles.badgeText, { color: colors.onStatus }]}>
                  {i.level === 'going' ? 'Going' : 'Maybe'}
                </Text>
              </View>
            </Card>
          );
        })
      )}

      <Text style={[styles.section, { color: colors.labelSecondary }]}>Favorite artists</Text>
      {favorites.length === 0 ? (
        <Text style={[styles.empty, { color: colors.labelSecondary }]}>None yet.</Text>
      ) : (
        <View style={styles.chips}>
          {favorites.map((a) => (
            <View key={a.name} style={styles.favChip}>
              <Icon name="favorite" size={12} color={colors.accent} />
              <Chip label={a.name} />
            </View>
          ))}
        </View>
      )}

      <Text style={[styles.section, { color: colors.labelSecondary }]}>Liked artists</Text>
      {liked.length === 0 ? (
        <Text style={[styles.empty, { color: colors.labelSecondary }]}>None yet.</Text>
      ) : (
        <View style={styles.chips}>
          {liked.map((a) => <Chip key={a.name} label={a.name} />)}
        </View>
      )}

      <Text style={[styles.section, { color: colors.labelSecondary }]}>Genres</Text>
      {profile.genres.length === 0 ? (
        <Text style={[styles.empty, { color: colors.labelSecondary }]}>None yet.</Text>
      ) : (
        <View style={styles.chips}>
          {profile.genres.map((g) => <Chip key={g} label={g} />)}
        </View>
      )}

      <View style={styles.dangerRow}>
        <TouchableOpacity
          style={[styles.outlineBtn, { borderColor: colors.separator }]}
          onPress={confirmUnfriend}
        >
          <Text style={[styles.outlineBtnText, { color: colors.labelSecondary }]}>Unfriend</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.dangerBtn, { backgroundColor: colors.destructive }]}
          onPress={confirmBlock}
        >
          <Text style={[styles.dangerBtnText, { color: colors.onStatus }]}>Block</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

// Layout/metrics only — colors come from the theme at render time.
const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  container: { padding: spacing.lg },
  header: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginBottom: spacing.sm },
  headerText: { flex: 1, gap: 2 },
  name: { ...typeScale.title, fontSize: 24 },
  username: { ...typeScale.body },
  meta: { ...typeScale.callout },
  section: {
    ...typeScale.caption, fontWeight: '700', textTransform: 'uppercase',
    marginTop: spacing.xl, marginBottom: spacing.sm,
  },
  empty: { ...typeScale.body },
  card: { marginBottom: spacing.sm, gap: 2 },
  eventName: { ...typeScale.headline },
  date: { ...typeScale.caption, marginTop: 2 },
  badge: {
    alignSelf: 'flex-start', marginTop: spacing.xs, borderRadius: radii.pill,
    paddingHorizontal: spacing.sm, paddingVertical: 2,
  },
  badgeText: { ...typeScale.caption, fontWeight: '700' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  favChip: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  dangerRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xxl, marginBottom: spacing.xl },
  outlineBtn: {
    flex: 1, borderWidth: 1, borderRadius: radii.md,
    padding: spacing.md, alignItems: 'center',
  },
  outlineBtnText: { ...typeScale.headline },
  dangerBtn: {
    flex: 1, borderRadius: radii.md,
    padding: spacing.md, alignItems: 'center',
  },
  dangerBtnText: { ...typeScale.headline },
});
