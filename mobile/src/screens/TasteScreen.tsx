import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, SectionList, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import {
  Artist, TaxonomyGenre, addArtist, addGenre, getGenreTaxonomy,
  getMyArtists, getMyGenres, removeArtist, removeGenre,
} from '../api/artists';

// Genres come from the TM taxonomy picker only — the API rejects free text.
function GenrePickerModal({ visible, onClose, myGenres, onPick }: {
  visible: boolean;
  onClose: () => void;
  myGenres: string[];
  onPick: (genre: string) => void;
}) {
  const [taxonomy, setTaxonomy] = useState<TaxonomyGenre[] | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (visible && taxonomy === null) {
      getGenreTaxonomy()
        .then(setTaxonomy)
        .catch(() => Alert.alert('Error', 'Could not load genres'));
    }
  }, [visible, taxonomy]);

  const toggleExpanded = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const sections = (taxonomy ?? []).map((g) => ({
    title: g.name,
    data: expanded.has(g.name) ? g.subgenres : [],
  }));

  const picked = (name: string) => myGenres.includes(name);

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={pickerStyles.container}>
        <View style={pickerStyles.header}>
          <Text style={pickerStyles.title}>Pick genres</Text>
          <TouchableOpacity onPress={onClose}>
            <Text style={pickerStyles.done}>Done</Text>
          </TouchableOpacity>
        </View>
        {taxonomy === null ? (
          <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#6200EE" />
        ) : (
          <SectionList
            sections={sections}
            keyExtractor={(item) => item}
            renderSectionHeader={({ section }) => (
              <View style={pickerStyles.genreRow}>
                <TouchableOpacity
                  style={pickerStyles.genreName}
                  onPress={() => onPick(section.title)}
                  disabled={picked(section.title)}
                >
                  <Text style={[pickerStyles.genreText, picked(section.title) && pickerStyles.pickedText]}>
                    {section.title}{picked(section.title) ? ' ✓' : ''}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => toggleExpanded(section.title)} hitSlop={12}>
                  <Text style={pickerStyles.expand}>
                    {expanded.has(section.title) ? '▾' : '▸'}
                  </Text>
                </TouchableOpacity>
              </View>
            )}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={pickerStyles.subgenreRow}
                onPress={() => onPick(item)}
                disabled={picked(item)}
              >
                <Text style={[pickerStyles.subgenreText, picked(item) && pickerStyles.pickedText]}>
                  {item}{picked(item) ? ' ✓' : ''}
                </Text>
              </TouchableOpacity>
            )}
            stickySectionHeadersEnabled={false}
          />
        )}
      </View>
    </Modal>
  );
}

export default function TasteScreen() {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [genres, setGenres] = useState<string[]>([]);
  const [artistInput, setArtistInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [addingArtist, setAddingArtist] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

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

  const handlePickGenre = async (genre: string) => {
    try {
      const updated = await addGenre(genre);
      setGenres(updated);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not add genre');
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
    <>
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
            <TouchableOpacity style={styles.pickBtn} onPress={() => setPickerOpen(true)}>
              <Text style={styles.pickBtnText}>+ Pick genres</Text>
            </TouchableOpacity>
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
      <GenrePickerModal
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        myGenres={genres}
        onPick={handlePickGenre}
      />
    </>
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
  pickBtn: {
    borderWidth: 1, borderColor: '#6200EE', borderStyle: 'dashed',
    borderRadius: 8, padding: 10, alignItems: 'center', marginBottom: 12,
  },
  pickBtnText: { color: '#6200EE', fontWeight: '600' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#f0e6ff', borderRadius: 20,
    paddingVertical: 6, paddingHorizontal: 12, marginBottom: 8,
  },
  chipText: { fontSize: 14, color: '#6200EE' },
  remove: { fontSize: 14, color: '#9c4dcc', fontWeight: '700' },
});

const pickerStyles = StyleSheet.create({
  container: { flex: 1, paddingTop: 56, paddingHorizontal: 16 },
  header: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 12,
  },
  title: { fontSize: 20, fontWeight: '700' },
  done: { fontSize: 16, color: '#6200EE', fontWeight: '600' },
  genreRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#eee',
    backgroundColor: '#fff',
  },
  genreName: { flex: 1 },
  genreText: { fontSize: 16, fontWeight: '600', color: '#222' },
  expand: { fontSize: 16, color: '#6200EE', paddingHorizontal: 8 },
  subgenreRow: { paddingVertical: 10, paddingLeft: 20 },
  subgenreText: { fontSize: 15, color: '#444' },
  pickedText: { color: '#00897B' },
});
