import { api } from './client';

export interface EventSearchResult {
  id: string;
  name: string;
  artist_name: string | null;
  venue_name: string | null;
  starts_at: string | null;
  genre: string | null;
  url: string | null;
  my_interest: 'going' | 'maybe' | null;
}

// Searches the cached metro events server-side (name/artist/venue) — never live TM.
export async function searchEvents(q: string): Promise<EventSearchResult[]> {
  const { data } = await api.get('/events/search', { params: { q } });
  return data;
}
