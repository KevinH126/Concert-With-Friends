import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, SectionList, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import {
  Artist, TaxonomyGenre, addArtist, addGenre, getGenreTaxonomy,
  getMyArtists, getMyGenres, removeArtist, removeGenre,
} from '../api/artists';
import { Button, Chip, Icon, Skeleton } from '../components';
import { radii, spacing, type as typeScale, useTheme } from '../theme';

// Genres come from the TM taxonomy picker only — the API rejects free text.
// Tapping toggles: unpicked adds, picked (✓) removes.
function GenrePickerModal({ visible, onClose, myGenres, onToggle }: {
  visible: boolean;
  onClose: () => void;
  myGenres: string[];
  onToggle: (genre: string) => void;
}) {
  const { colors } = useTheme();
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
      <View style={[pickerStyles.container, { backgroundColor: colors.background }]}>
        <View style={pickerStyles.header}>
          <Text style={[pickerStyles.title, { color: colors.label }]}>Pick genres</Text>
          <TouchableOpacity onPress={onClose}>
            <Text style={[pickerStyles.done, { color: colors.accent }]}>Done</Text>
          </TouchableOpacity>
        </View>
        {taxonomy === null ? (
          <ActivityIndicator style={{ marginTop: spacing.xxl }} size="large" color={colors.accent} />
        ) : (
          <SectionList
            sections={sections}
            keyExtractor={(item) => item}
            renderSectionHeader={({ section }) => (
              <View style={[pickerStyles.genreRow, { borderBottomColor: colors.separator, backgroundColor: colors.background }]}>
                <TouchableOpacity
                  style={pickerStyles.genreName}
                  onPress={() => onToggle(section.title)}
                >
                  <View style={pickerStyles.pickedLine}>
                    <Text style={[
                      pickerStyles.genreText,
                      { color: picked(section.title) ? colors.accent : colors.label },
                    ]}>
                      {section.title}
                    </Text>
                    {picked(section.title) && <Icon name="check" size={14} color={colors.accent} />}
                  </View>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => toggleExpanded(section.title)} hitSlop={12}>
                  <Icon
                    name={expanded.has(section.title) ? 'chevronDown' : 'chevronRight'}
                    size={16}
                    color={colors.labelSecondary}
                  />
                </TouchableOpacity>
              </View>
            )}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={pickerStyles.subgenreRow}
                onPress={() => onToggle(item)}
              >
                <View style={pickerStyles.pickedLine}>
                  <Text style={[
                    pickerStyles.subgenreText,
                    { color: picked(item) ? colors.accent : colors.labelSecondary },
                  ]}>
                    {item}
                  </Text>
                  {picked(item) && <Icon name="check" size={13} color={colors.accent} />}
                </View>
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
  const { colors } = useTheme();
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

  const handleToggleGenre = async (genre: string) => {
    try {
      if (genres.includes(genre)) {
        await removeGenre(genre);
        setGenres((prev) => prev.filter((g) => g !== genre));
      } else {
        const updated = await addGenre(genre);
        setGenres(updated);
      }
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not update genre');
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

  if (loading) {
    return (
      <View style={[styles.container, { flex: 1, backgroundColor: colors.background }]}>
        <Skeleton width="45%" height={20} style={{ marginBottom: spacing.md }} />
        <Skeleton height={44} radius={radii.sm} style={{ marginBottom: spacing.lg }} />
        <View style={styles.chipRow}>
          <Skeleton width={90} height={30} radius={radii.pill} />
          <Skeleton width={70} height={30} radius={radii.pill} />
          <Skeleton width={110} height={30} radius={radii.pill} />
        </View>
      </View>
    );
  }

  return (
    <>
      <FlatList
        style={{ backgroundColor: colors.background }}
        ListHeaderComponent={
          <View>
            <Text style={[styles.sectionTitle, { color: colors.label }]}>Favorite Artists</Text>
            <View style={styles.row}>
              <TextInput
                style={[styles.input, { borderColor: colors.separator, color: colors.label, backgroundColor: colors.surface }]}
                placeholder="Artist name"
                placeholderTextColor={colors.labelTertiary}
                value={artistInput}
                onChangeText={setArtistInput}
                onSubmitEditing={handleAddArtist}
                returnKeyType="done"
              />
              <Button title="Add" onPress={handleAddArtist} loading={addingArtist} />
            </View>
            {artists.length === 0 && (
              <Text style={[styles.emptyHint, { color: colors.labelTertiary }]}>
                Add the artists you love — they’re the strongest signal for your feed.
              </Text>
            )}
          </View>
        }
        data={artists}
        keyExtractor={(a) => a.id}
        renderItem={({ item }) => (
          <View style={styles.chipWrap}>
            <Chip label={item.name} onRemove={() => handleRemoveArtist(item.id)} />
          </View>
        )}
        ListFooterComponent={
          <View>
            <Text style={[styles.sectionTitle, { color: colors.label, marginTop: spacing.xl }]}>Favorite Genres</Text>
            <TouchableOpacity
              style={[styles.pickBtn, { borderColor: colors.accent }]}
              onPress={() => setPickerOpen(true)}
            >
              <Icon name="add" size={16} color={colors.accent} />
              <Text style={[styles.pickBtnText, { color: colors.accent }]}>Pick genres</Text>
            </TouchableOpacity>
            {genres.length === 0 ? (
              <Text style={[styles.emptyHint, { color: colors.labelTertiary }]}>
                Pick a few genres to round out shows beyond your named artists.
              </Text>
            ) : (
              <View style={styles.chipRow}>
                {genres.map((g) => (
                  <Chip key={g} label={g} onRemove={() => handleRemoveGenre(g)} />
                ))}
              </View>
            )}
          </View>
        }
        contentContainerStyle={styles.container}
      />
      <GenrePickerModal
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        myGenres={genres}
        onToggle={handleToggleGenre}
      />
    </>
  );
}

// Layout/metrics only — colors come from the theme at render time.
const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  container: { padding: spacing.lg },
  sectionTitle: { ...typeScale.title, fontSize: 18, marginBottom: spacing.md },
  row: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  input: {
    flex: 1, borderWidth: 1, borderRadius: radii.sm,
    padding: spacing.md, fontSize: 15,
  },
  chipWrap: { marginBottom: spacing.sm, alignSelf: 'flex-start' },
  pickBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.xs,
    borderWidth: 1, borderStyle: 'dashed', borderRadius: radii.sm,
    padding: spacing.md, marginBottom: spacing.md,
  },
  pickBtnText: { ...typeScale.headline },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  emptyHint: { ...typeScale.callout, marginBottom: spacing.xs },
});

const pickerStyles = StyleSheet.create({
  container: { flex: 1, paddingTop: 56, paddingHorizontal: spacing.lg },
  header: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: spacing.md,
  },
  title: { ...typeScale.title, fontSize: 20 },
  done: { ...typeScale.headline },
  genreRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: spacing.md, borderBottomWidth: 1,
  },
  genreName: { flex: 1 },
  pickedLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  genreText: { ...typeScale.headline, fontSize: 16 },
  subgenreRow: { paddingVertical: spacing.sm + 2, paddingLeft: spacing.xl },
  subgenreText: { ...typeScale.body },
});
