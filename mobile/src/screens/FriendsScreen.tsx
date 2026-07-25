import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, Modal, ScrollView, Share,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import QRCode from 'react-native-qrcode-svg';
import {
  FriendRequests, FriendUser, SearchResult,
  acceptRequest, declineOrCancelRequest, getFriends, getRequests,
  searchUsers, sendRequest,
} from '../api/friends';
import { Invite, createInvite, redeemInvite } from '../api/invites';
import { Avatar, Button, Icon } from '../components';
import { radii, spacing, type as typeScale, useTheme } from '../theme';

export default function FriendsScreen() {
  const { colors } = useTheme();
  const navigation = useNavigation<any>();
  const [loading, setLoading] = useState(true);
  const [friends, setFriends] = useState<FriendUser[]>([]);
  const [requests, setRequests] = useState<FriendRequests>({ incoming: [], outgoing: [] });

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const [invite, setInvite] = useState<Invite | null>(null);
  const [inviteVisible, setInviteVisible] = useState(false);
  const [redeemVisible, setRedeemVisible] = useState(false);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [f, r] = await Promise.all([getFriends(), getRequests()]);
      setFriends(f);
      setRequests(r);
    } catch {
      Alert.alert('Error', 'Could not load friends');
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load().finally(() => setLoading(false));
    }, [load]),
  );

  const runSearch = async (q: string) => {
    setQuery(q);
    const trimmed = q.trim().toLowerCase();
    if (trimmed.length < 3) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      setResults(await searchUsers(trimmed));
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const openInvite = async () => {
    setBusy(true);
    try {
      const inv = await createInvite();
      setInvite(inv);
      setInviteVisible(true);
    } catch {
      Alert.alert('Error', 'Could not create an invite');
    } finally {
      setBusy(false);
    }
  };

  const shareInvite = async () => {
    if (!invite) return;
    await Share.share({
      message: `Join me on Concert With Friends! Open this link and follow the steps: ${invite.url}`,
    });
  };

  const submitCode = async () => {
    if (!code.trim()) return;
    setBusy(true);
    try {
      const friend = await redeemInvite(code);
      setRedeemVisible(false);
      setCode('');
      Alert.alert('Friend added!', `You and ${friend.display_name} are now friends.`);
      await load();
    } catch (e: any) {
      const status = e?.response?.status;
      const msg =
        status === 404 ? 'That code doesn’t exist. Double-check it and try again.'
        : status === 410 ? 'That invite has expired or is no longer valid.'
        : status === 400 ? 'You can’t redeem your own invite.'
        : 'Could not redeem the code.';
      Alert.alert('Error', msg);
    } finally {
      setBusy(false);
    }
  };

  const onSearchAction = async (r: SearchResult) => {
    try {
      if (r.friendship_status === 'none') {
        await sendRequest(r.id);
      } else if (r.friendship_status === 'pending_in') {
        await acceptRequest(r.id);
      } else if (r.friendship_status === 'pending_out') {
        await declineOrCancelRequest(r.id);
      } else {
        return; // already friends
      }
      await Promise.all([runSearch(query), load()]);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not update request');
    }
  };

  const actionLabel: Record<SearchResult['friendship_status'], string> = {
    none: 'Add',
    pending_out: 'Requested',
    pending_in: 'Accept',
    friends: 'Friends',
  };

  // A compact pill action on a person row. Filled accent = primary action; muted = settled.
  const SmallAction = ({ label, filled, muted, onPress }: {
    label: string; filled?: boolean; muted?: boolean; onPress: () => void;
  }) => (
    <TouchableOpacity
      style={[
        styles.smallBtn,
        filled && { backgroundColor: colors.accent },
        !filled && { borderWidth: 1, borderColor: muted ? colors.separator : colors.accent },
      ]}
      onPress={onPress}
      disabled={muted}
    >
      <Text style={[
        styles.smallBtnText,
        { color: filled ? colors.onAccent : muted ? colors.labelSecondary : colors.accent },
      ]}>
        {label}
      </Text>
    </TouchableOpacity>
  );

  // A person row: avatar + name/username + trailing content (actions or chevron).
  const PersonRow = ({ name, username, onPress, children }: {
    name: string; username?: string | null; onPress?: () => void; children?: React.ReactNode;
  }) => {
    const body = (
      <>
        <Avatar name={name} size={40} />
        <View style={styles.rowText}>
          <Text style={[styles.name, { color: colors.label }]}>{name}</Text>
          {username && <Text style={[styles.username, { color: colors.labelSecondary }]}>@{username}</Text>}
        </View>
        {children}
      </>
    );
    if (onPress) {
      return (
        <TouchableOpacity style={[styles.row, { backgroundColor: colors.surface }]} onPress={onPress}>
          {body}
        </TouchableOpacity>
      );
    }
    return <View style={[styles.row, { backgroundColor: colors.surface }]}>{body}</View>;
  };

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={styles.container}
    >
      <View style={styles.actionRow}>
        <Button title="Invite friends" onPress={openInvite} disabled={busy} style={{ flex: 1 }} />
        <Button title="Enter code" variant="secondary" onPress={() => setRedeemVisible(true)} style={{ flex: 1 }} />
      </View>

      <View style={[styles.search, { borderColor: colors.separator, backgroundColor: colors.surface }]}>
        <Icon name="search" size={17} color={colors.labelTertiary} />
        <TextInput
          style={[styles.searchInput, { color: colors.label }]}
          placeholder="Search by username (3+ letters)"
          placeholderTextColor={colors.labelTertiary}
          value={query}
          onChangeText={runSearch}
          autoCapitalize="none"
          autoCorrect={false}
        />
      </View>
      {searching && <ActivityIndicator size="small" color={colors.accent} style={{ marginBottom: spacing.sm }} />}
      {results.map((r) => (
        <PersonRow key={r.id} name={r.display_name} username={r.username}>
          <SmallAction
            label={actionLabel[r.friendship_status]}
            filled={r.friendship_status === 'none' || r.friendship_status === 'pending_in'}
            muted={r.friendship_status === 'friends' || r.friendship_status === 'pending_out'}
            onPress={() => onSearchAction(r)}
          />
        </PersonRow>
      ))}

      {requests.incoming.length > 0 && (
        <>
          <Text style={[styles.section, { color: colors.labelSecondary }]}>Friend requests</Text>
          {requests.incoming.map((u) => (
            <PersonRow key={u.id} name={u.display_name} username={u.username}>
              <SmallAction label="Accept" filled onPress={async () => { await acceptRequest(u.id); await load(); }} />
              <SmallAction label="Decline" muted onPress={async () => { await declineOrCancelRequest(u.id); await load(); }} />
            </PersonRow>
          ))}
        </>
      )}

      {requests.outgoing.length > 0 && (
        <>
          <Text style={[styles.section, { color: colors.labelSecondary }]}>Sent requests</Text>
          {requests.outgoing.map((u) => (
            <PersonRow key={u.id} name={u.display_name} username={u.username}>
              <SmallAction label="Cancel" muted onPress={async () => { await declineOrCancelRequest(u.id); await load(); }} />
            </PersonRow>
          ))}
        </>
      )}

      <Text style={[styles.section, { color: colors.labelSecondary }]}>Friends</Text>
      {friends.length === 0 ? (
        <Text style={[styles.empty, { color: colors.labelSecondary }]}>
          No friends yet. Send an invite to get started!
        </Text>
      ) : (
        friends.map((u) => (
          <PersonRow
            key={u.id}
            name={u.display_name}
            username={u.username}
            onPress={() => navigation.navigate('FriendProfile', { userId: u.id, displayName: u.display_name })}
          >
            <Icon name="chevronRight" size={18} color={colors.labelTertiary} />
          </PersonRow>
        ))
      )}

      {/* Invite modal: the QR is just the landing-page URL rendered */}
      <Modal visible={inviteVisible} transparent animationType="slide" onRequestClose={() => setInviteVisible(false)}>
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { backgroundColor: colors.surface }]}>
            <Text style={[styles.modalTitle, { color: colors.label }]}>Invite your friends</Text>
            <Text style={[styles.modalSub, { color: colors.labelSecondary }]}>
              Share the link, or have a friend scan this QR. The code works for up to{' '}
              {invite?.max_uses ?? 25} friends for 7 days.
            </Text>
            {invite && (
              <View style={styles.qrWrap}>
                <QRCode value={invite.url} size={180} />
              </View>
            )}
            <Text style={[styles.code, { color: colors.label }]}>{invite?.token}</Text>
            <Button title="Share link" onPress={shareInvite} icon="share" />
            <TouchableOpacity onPress={() => setInviteVisible(false)}>
              <Text style={[styles.modalClose, { color: colors.accent }]}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Redeem modal */}
      <Modal visible={redeemVisible} transparent animationType="slide" onRequestClose={() => setRedeemVisible(false)}>
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { backgroundColor: colors.surface }]}>
            <Text style={[styles.modalTitle, { color: colors.label }]}>Enter invite code</Text>
            <Text style={[styles.modalSub, { color: colors.labelSecondary }]}>
              Paste the code (or the whole link) your friend sent you.
            </Text>
            <View style={[styles.search, { borderColor: colors.separator, backgroundColor: colors.background }]}>
              <TextInput
                style={[styles.searchInput, { color: colors.label }]}
                placeholder="e.g. k7x2m9qp4a"
                placeholderTextColor={colors.labelTertiary}
                value={code}
                onChangeText={setCode}
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>
            <Button title="Redeem" onPress={submitCode} loading={busy} />
            <TouchableOpacity onPress={() => { setRedeemVisible(false); setCode(''); }}>
              <Text style={[styles.modalClose, { color: colors.accent }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

// Layout/metrics only — colors come from the theme at render time.
const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  container: { padding: spacing.lg },
  actionRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.lg },
  search: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    borderWidth: 1, borderRadius: radii.md, paddingHorizontal: spacing.md,
    height: 44, marginBottom: spacing.md,
  },
  searchInput: { flex: 1, ...typeScale.body, fontSize: 16 },
  section: {
    ...typeScale.caption, fontWeight: '700', textTransform: 'uppercase',
    marginTop: spacing.xl, marginBottom: spacing.sm,
  },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.md,
    borderRadius: radii.md, padding: spacing.md, marginBottom: spacing.sm,
  },
  rowText: { flex: 1 },
  name: { ...typeScale.headline, fontWeight: '500' },
  username: { ...typeScale.callout },
  smallBtn: { borderRadius: radii.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.xs + 2 },
  smallBtnText: { ...typeScale.caption, fontWeight: '600' },
  empty: { ...typeScale.body },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: spacing.xl },
  modalCard: { borderRadius: 16, padding: spacing.xl, gap: spacing.md },
  modalTitle: { ...typeScale.title, fontSize: 20, textAlign: 'center' },
  modalSub: { ...typeScale.body, textAlign: 'center' },
  qrWrap: { alignItems: 'center' },
  code: { fontSize: 24, fontWeight: '700', letterSpacing: 3, textAlign: 'center' },
  modalClose: { ...typeScale.headline, textAlign: 'center', marginTop: spacing.xs },
});
