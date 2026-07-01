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

export default function FriendsScreen() {
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
    pending_out: 'Requested ×',
    pending_in: 'Accept',
    friends: 'Friends ✓',
  };

  if (loading) {
    return <ActivityIndicator style={styles.center} size="large" color="#6200EE" />;
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.actionRow}>
        <TouchableOpacity style={styles.primaryBtn} onPress={openInvite} disabled={busy}>
          <Text style={styles.primaryBtnText}>Invite friends</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryBtn} onPress={() => setRedeemVisible(true)}>
          <Text style={styles.secondaryBtnText}>Enter invite code</Text>
        </TouchableOpacity>
      </View>

      <TextInput
        style={styles.search}
        placeholder="Search by username (3+ letters)"
        value={query}
        onChangeText={runSearch}
        autoCapitalize="none"
        autoCorrect={false}
      />
      {searching && <ActivityIndicator size="small" color="#6200EE" />}
      {results.map((r) => (
        <View key={r.id} style={styles.row}>
          <View style={styles.rowText}>
            <Text style={styles.name}>{r.display_name}</Text>
            <Text style={styles.username}>@{r.username}</Text>
          </View>
          <TouchableOpacity
            style={[styles.smallBtn, r.friendship_status === 'friends' && styles.smallBtnMuted]}
            onPress={() => onSearchAction(r)}
          >
            <Text style={styles.smallBtnText}>{actionLabel[r.friendship_status]}</Text>
          </TouchableOpacity>
        </View>
      ))}

      {requests.incoming.length > 0 && (
        <>
          <Text style={styles.section}>Friend requests</Text>
          {requests.incoming.map((u) => (
            <View key={u.id} style={styles.row}>
              <View style={styles.rowText}>
                <Text style={styles.name}>{u.display_name}</Text>
                {u.username && <Text style={styles.username}>@{u.username}</Text>}
              </View>
              <TouchableOpacity
                style={styles.smallBtn}
                onPress={async () => { await acceptRequest(u.id); await load(); }}
              >
                <Text style={styles.smallBtnText}>Accept</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.smallBtnOutline}
                onPress={async () => { await declineOrCancelRequest(u.id); await load(); }}
              >
                <Text style={styles.smallBtnOutlineText}>Decline</Text>
              </TouchableOpacity>
            </View>
          ))}
        </>
      )}

      {requests.outgoing.length > 0 && (
        <>
          <Text style={styles.section}>Sent requests</Text>
          {requests.outgoing.map((u) => (
            <View key={u.id} style={styles.row}>
              <View style={styles.rowText}>
                <Text style={styles.name}>{u.display_name}</Text>
                {u.username && <Text style={styles.username}>@{u.username}</Text>}
              </View>
              <TouchableOpacity
                style={styles.smallBtnOutline}
                onPress={async () => { await declineOrCancelRequest(u.id); await load(); }}
              >
                <Text style={styles.smallBtnOutlineText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          ))}
        </>
      )}

      <Text style={styles.section}>Friends</Text>
      {friends.length === 0 ? (
        <Text style={styles.empty}>No friends yet. Send an invite to get started!</Text>
      ) : (
        friends.map((u) => (
          <TouchableOpacity
            key={u.id}
            style={styles.row}
            onPress={() => navigation.navigate('FriendProfile', { userId: u.id, displayName: u.display_name })}
          >
            <View style={styles.rowText}>
              <Text style={styles.name}>{u.display_name}</Text>
              {u.username && <Text style={styles.username}>@{u.username}</Text>}
            </View>
            <Text style={styles.chevron}>{'›'}</Text>
          </TouchableOpacity>
        ))
      )}

      {/* Invite modal: the QR is just the landing-page URL rendered */}
      <Modal visible={inviteVisible} transparent animationType="slide" onRequestClose={() => setInviteVisible(false)}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Invite your friends</Text>
            <Text style={styles.modalSub}>
              Share the link, or have a friend scan this QR. The code works for up to{' '}
              {invite?.max_uses ?? 25} friends for 7 days.
            </Text>
            {invite && (
              <View style={styles.qrWrap}>
                <QRCode value={invite.url} size={180} />
              </View>
            )}
            <Text style={styles.code}>{invite?.token}</Text>
            <TouchableOpacity style={styles.primaryBtn} onPress={shareInvite}>
              <Text style={styles.primaryBtnText}>Share link</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setInviteVisible(false)}>
              <Text style={styles.modalClose}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Redeem modal */}
      <Modal visible={redeemVisible} transparent animationType="slide" onRequestClose={() => setRedeemVisible(false)}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Enter invite code</Text>
            <Text style={styles.modalSub}>Paste the code (or the whole link) your friend sent you.</Text>
            <TextInput
              style={styles.search}
              placeholder="e.g. k7x2m9qp4a"
              value={code}
              onChangeText={setCode}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TouchableOpacity style={styles.primaryBtn} onPress={submitCode} disabled={busy}>
              {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>Redeem</Text>}
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setRedeemVisible(false); setCode(''); }}>
              <Text style={styles.modalClose}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  container: { padding: 16 },
  actionRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  primaryBtn: {
    flex: 1, backgroundColor: '#6200EE', borderRadius: 8,
    padding: 12, alignItems: 'center',
  },
  primaryBtnText: { color: '#fff', fontWeight: '600' },
  secondaryBtn: {
    flex: 1, borderWidth: 1, borderColor: '#6200EE', borderRadius: 8,
    padding: 12, alignItems: 'center',
  },
  secondaryBtnText: { color: '#6200EE', fontWeight: '600' },
  search: {
    borderWidth: 1, borderColor: '#ddd', borderRadius: 8,
    padding: 12, marginBottom: 12, fontSize: 16,
  },
  section: { fontSize: 13, fontWeight: '700', color: '#888', textTransform: 'uppercase', marginTop: 20, marginBottom: 8 },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#fff', borderRadius: 10, padding: 12, marginBottom: 8,
  },
  rowText: { flex: 1 },
  name: { fontSize: 16, fontWeight: '500' },
  username: { fontSize: 13, color: '#888' },
  chevron: { fontSize: 22, color: '#bbb' },
  smallBtn: { backgroundColor: '#6200EE', borderRadius: 6, paddingHorizontal: 12, paddingVertical: 6 },
  smallBtnMuted: { backgroundColor: '#9e9e9e' },
  smallBtnText: { color: '#fff', fontWeight: '600', fontSize: 13 },
  smallBtnOutline: { borderWidth: 1, borderColor: '#bbb', borderRadius: 6, paddingHorizontal: 12, paddingVertical: 6 },
  smallBtnOutlineText: { color: '#666', fontWeight: '600', fontSize: 13 },
  empty: { color: '#888', fontSize: 14 },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: 24 },
  modalCard: { backgroundColor: '#fff', borderRadius: 16, padding: 24, alignItems: 'stretch' },
  modalTitle: { fontSize: 20, fontWeight: '700', textAlign: 'center', marginBottom: 8 },
  modalSub: { fontSize: 14, color: '#666', textAlign: 'center', marginBottom: 16 },
  qrWrap: { alignItems: 'center', marginBottom: 12 },
  code: { fontSize: 24, fontWeight: '700', letterSpacing: 3, textAlign: 'center', marginBottom: 16 },
  modalClose: { color: '#6200EE', textAlign: 'center', marginTop: 14, fontWeight: '600' },
});
