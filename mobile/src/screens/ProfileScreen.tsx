import React, { useEffect, useState } from 'react';
import {
  Alert, ScrollView, StyleSheet, Text, TextInput,
  TouchableOpacity, View,
} from 'react-native';
import { updateProfile } from '../api/auth';
import { useAuth } from '../context/AuthContext';

export default function ProfileScreen() {
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

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.name}>{user?.display_name}</Text>
      {user?.username && <Text style={styles.usernameLine}>@{user.username}</Text>}
      <Text style={styles.email}>{user?.email}</Text>

      <View style={styles.section}>
        <Text style={styles.label}>Username</Text>
        <Text style={styles.hint}>How friends find you in search. Lowercase letters, numbers, underscores.</Text>
        <TextInput
          style={styles.input}
          value={username}
          onChangeText={(t) => setUsername(t.toLowerCase())}
          placeholder="e.g. kevin_h"
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TouchableOpacity style={styles.button} onPress={saveUsername} disabled={saving}>
          <Text style={styles.buttonText}>{saving ? 'Saving…' : 'Save username'}</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Home Metro (Ticketmaster DMA ID)</Text>
        <Text style={styles.hint}>
          Find your metro ID at ticketmaster.com/discovery/v2/dmas.json
        </Text>
        <TextInput
          style={styles.input}
          value={metroId}
          onChangeText={setMetroId}
          placeholder="e.g. 286 for Los Angeles"
          keyboardType="numeric"
        />
        <TouchableOpacity style={styles.button} onPress={saveMetro} disabled={saving}>
          <Text style={styles.buttonText}>{saving ? 'Saving…' : 'Save'}</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
        <Text style={styles.logoutText}>Sign out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 24, backgroundColor: '#fff', flexGrow: 1 },
  name: { fontSize: 24, fontWeight: '700' },
  usernameLine: { fontSize: 15, color: '#6200EE', marginTop: 2 },
  email: { fontSize: 14, color: '#666', marginBottom: 32 },
  section: { marginBottom: 24 },
  label: { fontSize: 15, fontWeight: '600', marginBottom: 4 },
  hint: { fontSize: 12, color: '#888', marginBottom: 8 },
  input: {
    borderWidth: 1, borderColor: '#ddd', borderRadius: 8,
    padding: 10, fontSize: 15, marginBottom: 10,
  },
  button: {
    backgroundColor: '#6200EE', borderRadius: 8,
    padding: 12, alignItems: 'center',
  },
  buttonText: { color: '#fff', fontWeight: '600' },
  logoutBtn: { marginTop: 'auto', padding: 12, alignItems: 'center' },
  logoutText: { color: '#d32f2f', fontSize: 15 },
});
