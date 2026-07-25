import React, { useEffect, useState } from 'react';
import {
  Alert, ScrollView, StyleSheet, Text, TextInput,
  TouchableOpacity, View,
} from 'react-native';
import { updateProfile } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components';
import { radii, spacing, type as typeScale, useTheme } from '../theme';

export default function ProfileScreen() {
  const { colors } = useTheme();
  const { user, refresh, logout } = useAuth();
  const [metroId, setMetroId] = useState(user?.home_metro_id ?? '');
  const [username, setUsername] = useState(user?.username ?? '');
  const [saving, setSaving] = useState(false);

  // Keep the fields in sync once the user object loads/changes.
  useEffect(() => {
    setMetroId(user?.home_metro_id ?? '');
    setUsername(user?.username ?? '');
  }, [user?.home_metro_id, user?.username]);

  const saveMetro = async () => {
    setSaving(true);
    try {
      await updateProfile({ home_metro_id: metroId.trim() || undefined });
      await refresh();
      Alert.alert('Saved', 'Home metro updated');
    } catch {
      Alert.alert('Error', 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  const saveUsername = async () => {
    const trimmed = username.trim().toLowerCase();
    if (!/^[a-z0-9_]{3,20}$/.test(trimmed)) {
      Alert.alert('Invalid username', 'Use 3-20 lowercase letters, numbers, or underscores.');
      return;
    }
    setSaving(true);
    try {
      await updateProfile({ username: trimmed });
      await refresh();
      Alert.alert('Saved', 'Username updated');
    } catch (e: any) {
      const msg = e?.response?.status === 409 ? 'That username is taken.' : 'Could not save';
      Alert.alert('Error', msg);
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = [
    styles.input,
    { borderColor: colors.separator, color: colors.label, backgroundColor: colors.surface },
  ];

  return (
    <ScrollView contentContainerStyle={[styles.container, { backgroundColor: colors.background }]}>
      <Text style={[styles.name, { color: colors.label }]}>{user?.display_name}</Text>
      {user?.username && <Text style={[styles.usernameLine, { color: colors.accent }]}>@{user.username}</Text>}
      <Text style={[styles.email, { color: colors.labelSecondary }]}>{user?.email}</Text>

      <View style={styles.section}>
        <Text style={[styles.label, { color: colors.label }]}>Username</Text>
        <Text style={[styles.hint, { color: colors.labelTertiary }]}>
          How friends find you in search. Lowercase letters, numbers, underscores.
        </Text>
        <TextInput
          style={inputStyle}
          value={username}
          onChangeText={(t) => setUsername(t.toLowerCase())}
          placeholder="e.g. kevin_h"
          placeholderTextColor={colors.labelTertiary}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <Button title="Save username" onPress={saveUsername} loading={saving} />
      </View>

      <View style={styles.section}>
        <Text style={[styles.label, { color: colors.label }]}>Home Metro (Ticketmaster DMA ID)</Text>
        <Text style={[styles.hint, { color: colors.labelTertiary }]}>
          Find your metro ID at ticketmaster.com/discovery/v2/dmas.json
        </Text>
        <TextInput
          style={inputStyle}
          value={metroId}
          onChangeText={setMetroId}
          placeholder="e.g. 286 for Los Angeles"
          placeholderTextColor={colors.labelTertiary}
          keyboardType="numeric"
        />
        <Button title="Save" onPress={saveMetro} loading={saving} />
      </View>

      <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
        <Text style={[styles.logoutText, { color: colors.maybe }]}>Sign out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

// Layout/metrics only — colors come from the theme at render time.
const styles = StyleSheet.create({
  container: { padding: spacing.xl, flexGrow: 1 },
  name: { ...typeScale.title, fontSize: 24 },
  usernameLine: { ...typeScale.body, marginTop: 2 },
  email: { ...typeScale.callout, marginBottom: spacing.xxl },
  section: { marginBottom: spacing.xl },
  label: { ...typeScale.headline, marginBottom: spacing.xs },
  hint: { ...typeScale.caption, marginBottom: spacing.sm },
  input: {
    borderWidth: 1, borderRadius: radii.sm,
    padding: spacing.md, fontSize: 15, marginBottom: spacing.md,
  },
  logoutBtn: { marginTop: 'auto', padding: spacing.md, alignItems: 'center' },
  logoutText: { ...typeScale.body, fontSize: 15 },
});
