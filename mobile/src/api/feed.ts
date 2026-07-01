import { api } from './client';

export interface FriendGoing {
  user_id: string;
  display_name: string;
  level: 'going' | 'maybe';
}

export interface FeedEvent {
  id: string;
  name: string;
  artist_name: string | null;
  venue_name: string | null;
  starts_at: string | null;
  genre: string | null;
  my_interest: 'going' | 'maybe' | null;
  my_interest_visibility: 'shared' | 'private' | null;
  friends_going: FriendGoing[];
}

export async function getFeed(): Promise<FeedEvent[]> {
  const { data } = await api.get('/feed');
  return data;
}

export async function setInterest(
  eventId: string,
  level: 'going' | 'maybe',
  visibility: 'shared' | 'private' = 'shared',
): Promise<void> {
  await api.put(`/feed/events/${eventId}/interest`, { level, visibility });
}

export async function removeInterest(eventId: string): Promise<void> {
  await api.delete(`/feed/events/${eventId}/interest`);
}
