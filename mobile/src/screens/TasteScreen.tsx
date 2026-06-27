import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import {
  Artist, addArtist, addGenre, getMyArtists, getMyGenres, removeArtist, removeGenre,
} from '../api/artists';

export default function TasteScreen() {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [genres, setGenres] = useState<string[]>([]);
  const [artistInput, setArtistInput] = useState('');
  const [genreInput, setGenreInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [addingArtist, setAddingArtist] = useState(false);
  const [addingGenre, setAddingGenre] = useState(false);

  useEffect(() => {
    Promise.all([getMyArtists(), getMyGenres()])
      .then(([a, g]) => { setArtists(a); setGenres(g); })
      .catch(() => Alert.alert('Error', 'Could not load taste'))
      .finally(() => setLoading(false));
  }, []);

  const handleAddArtist = async () => {
    const name = artistInput.trim();
    if (!name) return;
    setAddingArtist(true);
    try {
      const artist = await addArtist(name);
      setArtists((prev) => [...prev.filter((a) => a.id !== artist.id), artist]);
      setArtistInput('');
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not add artist');
    } finally {
      setAddingArtist(false);
    }
  };

  const handleRemoveArtist = async (id: string) => {
    try {
      await removeArtist(id);
      setArtists((prev) => prev.filter((a) => a.id !== id));
    } catch {
      Alert.alert('Error', 'Could not remove artist');
    }
  };

  const handleAddGenre = async () => {
    const genre = genreInput.trim();
    if (!genre) return;
    setAddingGenre(true);
    try {
      const updated = await addGenre(genre);
      setGenres(updated);
      setGenreInput('');
    } catch {
      Alert.alert('Error', 'Could not add genre');
    } finally {
      setAddingGenre(false);
    }
  };

  const handleRemoveGenre = async (genre: string) => {
    try {
      await removeGenre(genre);
      setGenres((prev) => prev.filter((g) => g !== genre));
    } catch {
      Alert.alert('Error', 'Could not remove genre');
    }
  };

  if (loading) return <ActivityIndicator style={styles.center} size="large" color="#6200EE" />;

  return (
    <FlatList
      ListHeaderComponent={
        <View>
          <Text style={styles.sectionTitle}>Favorite Artists</Text>
          <View style={styles.row}>
            <TextInput
              style={styles.input}
              placeholder="Artist name"
              value={artistInput}
              onChangeText={setArtistInput}
              onSubmitEditing={handleAddArtist}
              returnKeyType="done"
            />
            <TouchableOpacity style={styles.addBtn} onPress={handleAddArtist} disabled={addingArtist}>
              <Text style={styles.addBtnText}>{addingArtist ? '...' : 'Add'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      }
      data={artists}
      keyExtractor={(a) => a.id}
      renderItem={({ item }) => (
        <View style={styles.chip}>
          <Text style={styles.chipText}>{item.name}</Text>
          <TouchableOpacity onPress={() => handleRemoveArtist(item.id)}>
            <Text style={styles.remove}>✕</Text>
          </TouchableOpacity>
        </View>
      )}
      ListFooterComponent={
        <View>
          <Text style={[styles.sectionTitle, { marginTop: 24 }]}>Favorite Genres</Text>
          <View style={styles.row}>
            <TextInput
              style={styles.input}
              placeholder="e.g. Rock, Jazz, Pop"
              value={genreInput}
              onChangeText={setGenreInput}
              onSubmitEditing={handleAddGenre}
              returnKeyType="done"
            />
            <TouchableOpacity style={styles.addBtn} onPress={handleAddGenre} disabled={addingGenre}>
              <Text style={styles.addBtnText}>{addingGenre ? '...' : 'Add'}</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.chipRow}>
            {genres.map((g) => (
              <View key={g} style={styles.chip}>
                <Text style={styles.chipText}>{g}</Text>
                <TouchableOpacity onPress={() => handleRemoveGenre(g)}>
                  <Text style={styles.remove}>✕</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        </View>
      }
      contentContainerStyle={styles.container}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  container: { padding: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '700', marginBottom: 12 },
  row: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  input: {
    flex: 1, borderWidth: 1, borderColor: '#ddd',
    borderRadius: 8, padding: 10, fontSize: 15,
  },
  addBtn: {
    backgroundColor: '#6200EE', borderRadius: 8,
    paddingHorizontal: 16, justifyContent: 'center',
  },
  addBtnText: { color: '#fff', fontWeight: '600' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#f0e6ff', borderRadius: 20,
    paddingVertical: 6, paddingHorizontal: 12, marginBottom: 8,
  },
  chipText: { fontSize: 14, color: '#6200EE' },
  remove: { fontSize: 14, color: '#9c4dcc', fontWeight: '700' },
});
