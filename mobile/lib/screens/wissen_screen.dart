import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';

/// Die DRK-Wissensdatenbank.
///
/// Der mitgelieferte Grundbestand stammt aus öffentlichen Quellen — vor allem
/// dem Rettungsdienstbedarfsplan des Kreises. Die AAO selbst ist nicht
/// öffentlich; wer sie kennt, trägt sie hier ein. Eigene Einträge wirken
/// genauso auf die Lagebewertung wie die recherchierten.
class WissenScreen extends StatefulWidget {
  const WissenScreen({super.key});

  @override
  State<WissenScreen> createState() => _WissenScreenState();
}

class _WissenScreenState extends State<WissenScreen> {
  List<KnowledgeEntryData> _entries = [];
  bool _loading = true;
  String? _kindFilter;
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final api = context.read<AppState>().api;
    final entries = await api.fetchKnowledge(
      kind: _kindFilter,
      query: _searchController.text.trim(),
    );
    if (!mounted) return;
    setState(() {
      _entries = entries;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final eigene = _entries.where((e) => !e.isSeed).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Wissensdatenbank'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Eintrag hinzufügen',
            onPressed: _openEditor,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              controller: _searchController,
              style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
              decoration: InputDecoration(
                hintText: 'Suchen — z.B. MANV, Betreuungsplatz, Hochwasser',
                hintStyle: const TextStyle(
                    color: AppColors.textDim, fontSize: 13),
                prefixIcon: const Icon(Icons.search,
                    color: AppColors.textMuted, size: 20),
                filled: true,
                fillColor: AppColors.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.border),
                ),
                contentPadding: const EdgeInsets.symmetric(vertical: 4),
              ),
              onSubmitted: (_) => _load(),
            ),
          ),
          SizedBox(
            height: 38,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                _chip('Alle', null),
                ...kKnowledgeKindLabels.entries
                    .map((e) => _chip(e.value, e.key)),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
            child: Row(
              children: [
                Text(
                  '${_entries.length} Einträge',
                  style: const TextStyle(
                      color: AppColors.textMuted, fontSize: 11),
                ),
                if (eigene > 0) ...[
                  const Text(' · ',
                      style: TextStyle(
                          color: AppColors.textDim, fontSize: 11)),
                  Text(
                    '$eigene eigene',
                    style: const TextStyle(
                        color: AppColors.purpleLight, fontSize: 11),
                  ),
                ],
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(color: AppColors.drkRed))
                : _entries.isEmpty
                    ? const Center(
                        child: Text('Nichts gefunden',
                            style: TextStyle(color: AppColors.textMuted)))
                    : RefreshIndicator(
                        onRefresh: _load,
                        color: AppColors.drkRed,
                        child: ListView.builder(
                          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                          itemCount: _entries.length,
                          itemBuilder: (_, i) => _entryCard(_entries[i]),
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _chip(String label, String? kind) {
    final active = _kindFilter == kind;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: GestureDetector(
        onTap: () {
          setState(() => _kindFilter = kind);
          _load();
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          decoration: BoxDecoration(
            color: active ? AppColors.drkRed : AppColors.surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
                color: active ? AppColors.drkRed : AppColors.border),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: active ? Colors.white : AppColors.textSecondary,
              fontSize: 12,
            ),
          ),
        ),
      ),
    );
  }

  Widget _entryCard(KnowledgeEntryData e) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 14),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
          title: Text(
            e.title,
            style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 14,
                fontWeight: FontWeight.w600),
          ),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Row(
              children: [
                Icon(
                  e.isOfficial ? Icons.verified_outlined : Icons.edit_note,
                  size: 12,
                  color: e.isOfficial
                      ? AppColors.green
                      : AppColors.purpleLight,
                ),
                const SizedBox(width: 4),
                Text(
                  '${kKnowledgeKindLabels[e.kind] ?? e.kind} · '
                  '${kKnowledgeScopeLabels[e.scope] ?? e.scope}',
                  style: const TextStyle(
                      color: AppColors.textMuted, fontSize: 11),
                ),
              ],
            ),
          ),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                e.body,
                style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12.5,
                    height: 1.5),
              ),
            ),
            if (e.tags.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: e.tags
                    .map((t) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppColors.surfaceLight,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(t,
                              style: const TextStyle(
                                  color: AppColors.textMuted, fontSize: 10)),
                        ))
                    .toList(),
              ),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Text(
                    e.source == null
                        ? 'Eigener Eintrag'
                        : 'Quelle: ${e.source}'
                            '${e.sourceDate != null ? " (${e.sourceDate})" : ""}',
                    style: const TextStyle(
                        color: AppColors.textDim, fontSize: 10),
                  ),
                ),
                if (!e.isSeed)
                  TextButton.icon(
                    onPressed: () => _confirmDelete(e),
                    icon: const Icon(Icons.delete_outline, size: 15),
                    label: const Text('Löschen',
                        style: TextStyle(fontSize: 11)),
                    style: TextButton.styleFrom(
                        foregroundColor: AppColors.redLight),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmDelete(KnowledgeEntryData e) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Eintrag löschen?',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16)),
        content: Text(e.title,
            style: const TextStyle(
                color: AppColors.textSecondary, fontSize: 13)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Abbrechen',
                style: TextStyle(color: AppColors.textMuted)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Löschen',
                style: TextStyle(color: AppColors.redLight)),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final success = await context.read<AppState>().api.deleteKnowledge(e.id);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(success ? 'Gelöscht' : 'Löschen fehlgeschlagen'),
        backgroundColor: success ? AppColors.green : AppColors.red,
      ),
    );
    if (success) _load();
  }

  void _openEditor() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => _WissenEditor(onSaved: _load),
    );
  }
}

/// Formular für eigenes Wissen — AAO-Auszüge, interne Planungen, Erfahrungen.
class _WissenEditor extends StatefulWidget {
  final VoidCallback onSaved;
  const _WissenEditor({required this.onSaved});

  @override
  State<_WissenEditor> createState() => _WissenEditorState();
}

class _WissenEditorState extends State<_WissenEditor> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  final _tags = TextEditingController();
  final _source = TextEditingController();
  String _kind = 'ausloeser';
  String _scope = 'troisdorf';
  final Set<String> _categories = {};
  bool _saving = false;

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    _tags.dispose();
    _source.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_title.text.trim().isEmpty || _body.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Titel und Inhalt werden gebraucht'),
          backgroundColor: AppColors.orange,
        ),
      );
      return;
    }
    setState(() => _saving = true);
    final ok = await context.read<AppState>().api.addKnowledge(
          kind: _kind,
          scope: _scope,
          title: _title.text.trim(),
          body: _body.text.trim(),
          categories: _categories.toList(),
          tags: _tags.text
              .split(',')
              .map((t) => t.trim())
              .where((t) => t.isNotEmpty)
              .toList(),
          source: _source.text.trim().isEmpty ? null : _source.text.trim(),
        );
    if (!mounted) return;
    setState(() => _saving = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok ? 'Eintrag gespeichert' : 'Speichern fehlgeschlagen'),
        backgroundColor: ok ? AppColors.green : AppColors.red,
      ),
    );
    if (ok) {
      Navigator.pop(context);
      widget.onSaved();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Eigenes Wissen einpflegen',
                  style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 17,
                      fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              const Text(
                'Was hier steht, fließt in die Lagebewertung und den '
                'KI-Bericht ein — gleichberechtigt neben den recherchierten '
                'Einträgen.',
                style: TextStyle(
                    color: AppColors.textMuted, fontSize: 11, height: 1.4),
              ),
              const SizedBox(height: 16),
              _field(_title, 'Titel', 'z.B. AAO-Stichwort MANV 20 Troisdorf'),
              const SizedBox(height: 12),
              _field(_body, 'Inhalt',
                  'Was gilt, wer läuft, ab wann — so genau wie möglich',
                  maxLines: 7),
              const SizedBox(height: 12),
              _dropdown('Art', _kind, kKnowledgeKindLabels,
                  (v) => setState(() => _kind = v)),
              const SizedBox(height: 12),
              _dropdown('Bereich', _scope, kKnowledgeScopeLabels,
                  (v) => setState(() => _scope = v)),
              const SizedBox(height: 12),
              const Text('Betroffene Kategorien',
                  style: TextStyle(
                      color: AppColors.textSecondary, fontSize: 12)),
              const SizedBox(height: 6),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: _kategorieAuswahl.entries.map((entry) {
                  final active = _categories.contains(entry.key);
                  return GestureDetector(
                    onTap: () => setState(() {
                      active
                          ? _categories.remove(entry.key)
                          : _categories.add(entry.key);
                    }),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: active
                            ? AppColors.drkRed.withValues(alpha: 0.2)
                            : AppColors.surfaceLight,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                            color: active
                                ? AppColors.drkRed
                                : AppColors.border),
                      ),
                      child: Text(entry.value,
                          style: TextStyle(
                              color: active
                                  ? AppColors.drkRedAccent
                                  : AppColors.textSecondary,
                              fontSize: 11)),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 12),
              _field(_tags, 'Schlagworte (Komma-getrennt)',
                  'MANV, Alarmstichwort, Bereitstellungsraum'),
              const SizedBox(height: 12),
              _field(_source, 'Herkunft (optional)',
                  'z.B. AAO Rhein-Sieg-Kreis, Stand 2025'),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _saving ? null : _save,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.drkRed,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: _saving
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white))
                      : const Text('Speichern'),
                ),
              ),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }

  Widget _field(TextEditingController c, String label, String hint,
      {int maxLines = 1}) {
    return TextField(
      controller: c,
      maxLines: maxLines,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: AppColors.textMuted, fontSize: 12),
        hintText: hint,
        hintStyle: const TextStyle(color: AppColors.textDim, fontSize: 12),
        filled: true,
        fillColor: AppColors.surfaceLight,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.border),
        ),
      ),
    );
  }

  Widget _dropdown(String label, String value, Map<String, String> options,
      ValueChanged<String> onChanged) {
    return InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: AppColors.textMuted, fontSize: 12),
        filled: true,
        fillColor: AppColors.surfaceLight,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          isDense: true,
          dropdownColor: AppColors.surfaceLight,
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
          items: options.entries
              .map((e) =>
                  DropdownMenuItem(value: e.key, child: Text(e.value)))
              .toList(),
          onChanged: (v) => v != null ? onChanged(v) : null,
        ),
      ),
    );
  }
}

/// Kategorien, denen ein Eintrag zugeordnet werden kann — dieselben Schlüssel
/// wie im Scoring, sonst würde der Eintrag nie herangezogen.
const Map<String, String> _kategorieAuswahl = {
  'water': 'Hochwasser',
  'weather': 'Wetter',
  'fire': 'Waldbrand',
  'traffic': 'Verkehr',
  'power': 'Stromnetz',
  'health': 'Gesundheit',
  'official_warning': 'Behördenwarnungen',
  'manv': 'MANV',
  'events': 'Veranstaltungen',
  'radiation': 'Strahlung',
  'air_quality': 'Luftqualität',
  'shipping': 'Schifffahrt',
};
