import { api } from './client';

export interface FriendUser {
  id: string;
  username: string | null;
  display_name: string;
}

export interface FriendRequests {
  incoming: FriendUser[];
  outgoing: FriendUser[];
}

export type FriendshipStatus = 'none' | 'pending_out' | 'pending_in' | 'friends';

export interface SearchResult {
  id: string;
  username: string;
  display_name: string;
  friendship_status: FriendshipStatus;
}

export interface ProfileArtist {
  name: string;
  weight: number; // liked=1, favorite=2
}

export interface ProfileInterest {
  event_id: string;
  event_name: string;
  venue_name: string | null;
  starts_at: string | null;
  level: 'going' | 'maybe';
}

export interface FriendProfile {
  id: string;
  username: string | null;
  display_name: string;
  home_metro_id: string | null;
  artists: ProfileArtist[];
  genres: string[];
  interests: ProfileInterest[];
}

export async function getFriends(): Promise<FriendUser[]> {
  const { data } = await api.get('/friends');
  return data;
}

export async function getRequests(): Promise<FriendRequests> {
  const { data } = await api.get('/friends/requests');
  return data;
}

export async function sendRequest(userId: string): Promise<void> {
  await api.post('/friends/requests', { user_id: userId });
}

export async function acceptRequest(requesterId: string): Promise<void> {
  await api.post(`/friends/requests/${requesterId}/accept`);
}

// Declines an incoming request from userId, or cancels my outgoing one to them.
export async function declineOrCancelRequest(userId: string): Promise<void> {
  await api.delete(`/friends/requests/${userId}`);
}

export async function unfriend(userId: string): Promise<void> {
  await api.delete(`/friends/${userId}`);
}

export async function blockUser(userId: string): Promise<void> {
  await api.post(`/friends/${userId}/block`);
}

export async function getFriendProfile(userId: string): Promise<FriendProfile> {
  const { data } = await api.get(`/friends/${userId}/profile`);
  return data;
}

export async function searchUsers(q: string): Promise<SearchResult[]> {
  const { data } = await api.get('/users/search', { params: { q } });
  return data;
}
