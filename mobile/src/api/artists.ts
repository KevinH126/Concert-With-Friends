import { api } from './client';

export interface Artist {
  id: string;
  name: string;
  tm_attraction_id: string | null;
  weight: number;
}

export async function getMyArtists(): Promise<Artist[]> {
  const { data } = await api.get('/artists');
  return data;
}

export async function addArtist(name: string, weight = 1): Promise<Artist> {
  const { data } = await api.post('/artists', { name, weight });
  return data;
}

export async function removeArtist(artistId: string): Promise<void> {
  await api.delete(`/artists/${artistId}`);
}

export async function getMyGenres(): Promise<string[]> {
  const { data } = await api.get('/genres');
  return data;
}

export interface TaxonomyGenre {
  name: string;
  subgenres: string[];
}

// The picker's data (TM taxonomy). POST /genres rejects anything not in it.
export async function getGenreTaxonomy(): Promise<TaxonomyGenre[]> {
  const { data } = await api.get('/genres/taxonomy');
  return data;
}

export async function addGenre(genre: string): Promise<string[]> {
  const { data } = await api.post('/genres', { genre });
  return data;
}

export async function removeGenre(genre: string): Promise<void> {
  await api.delete(`/genres/${encodeURIComponent(genre)}`);
}
