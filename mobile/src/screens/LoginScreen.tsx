import React, { useState } from 'react';
import {
  Alert, KeyboardAvoidingView, Platform,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { login, signup } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components';
import { radii, spacing, type as typeScale, useTheme } from '../theme';

export default function LoginScreen() {
  const { colors } = useTheme();
  const { refresh } = useAuth();
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!email || !password) return;
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        if (!displayName) {
          Alert.alert('Display name is required');
          return;
        }
        if (!/^[a-z0-9_]{3,20}$/.test(username)) {
          Alert.alert('Invalid username', 'Use 3-20 lowercase letters, numbers, or underscores.');
          return;
        }
        await signup(email, username, displayName, password);
      }
      await refresh();
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Something went wrong';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = [
    styles.input,
    { borderColor: colors.separator, color: colors.label, backgroundColor: colors.surface },
  ];

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <Text style={[styles.title, { color: colors.label }]}>Concert With Friends</Text>
      <Text style={[styles.subtitle, { color: colors.labelSecondary }]}>
        {mode === 'login' ? 'Sign in' : 'Create account'}
      </Text>

      {mode === 'signup' && (
        <>
          <TextInput
            style={inputStyle}
            placeholder="Display name"
            placeholderTextColor={colors.labelTertiary}
            value={displayName}
            onChangeText={setDisplayName}
            autoCapitalize="words"
          />
          <TextInput
            style={inputStyle}
            placeholder="Username (lowercase, for friends to find you)"
            placeholderTextColor={colors.labelTertiary}
            value={username}
            onChangeText={(t) => setUsername(t.toLowerCase())}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </>
      )}
      <TextInput
        style={inputStyle}
        placeholder="Email"
        placeholderTextColor={colors.labelTertiary}
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <TextInput
        style={inputStyle}
        placeholder="Password"
        placeholderTextColor={colors.labelTertiary}
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <Button
        title={mode === 'login' ? 'Sign in' : 'Sign up'}
        onPress={submit}
        loading={loading}
        style={{ marginTop: spacing.sm }}
      />

      <TouchableOpacity onPress={() => setMode(mode === 'login' ? 'signup' : 'login')}>
        <Text style={[styles.toggle, { color: colors.accent }]}>
          {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
        </Text>
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

// Layout/metrics only — colors come from the theme at render time.
const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: spacing.xl },
  title: { fontSize: 28, fontWeight: '700', textAlign: 'center', marginBottom: spacing.xs },
  subtitle: { ...typeScale.body, fontSize: 16, textAlign: 'center', marginBottom: spacing.xxl },
  input: {
    borderWidth: 1, borderRadius: radii.sm,
    padding: spacing.md, marginBottom: spacing.md, fontSize: 16,
  },
  toggle: { ...typeScale.callout, textAlign: 'center', marginTop: spacing.lg },
});
