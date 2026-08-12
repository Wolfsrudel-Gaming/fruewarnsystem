import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../models/categories.dart';
import '../services/app_state.dart';

/// Einsatz nachträglich melden — auch (und gerade) wenn es keinen Alarm gab.
/// Einsätze ohne Alarm sind die wichtigste Lernquelle: Sie zeigen dem System,
/// wo es blind war.
class EinsatzMeldenScreen extends StatefulWidget {
  const EinsatzMeldenScreen({super.key});

  @override
  State<EinsatzMeldenScreen> createState() => _EinsatzMeldenScreenState();
}

class _EinsatzMeldenScreenState extends State<EinsatzMeldenScreen> {
  String _category = 'water';
  final _titleController = TextEditingController();
  final _descController = TextEditingController();
  final _forcesController = TextEditingController();
  DateTime _occurredAt = DateTime.now();
  int _severity = 3;
  bool _saving = false;

  List<DeploymentData>? _recent;

  @override
  void initState() {
    super.initState();
    _loadRecent();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descController.dispose();
    _forcesController.dispose();
    super.dispose();
  }

  Future<void> _loadRecent() async {
    final api = context.read<AppState>().api;
    final list = await api.fetchDeployments(days: 90);
    if (mounted) setState(() => _recent = list);
  }

  Future<void> _pickDateTime() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _occurredAt,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
      builder: (context, child) => Theme(
        data: ThemeData.dark().copyWith(
          colorScheme: const ColorScheme.dark(
            primary: AppColors.drkRed,
            surface: AppColors.surface,
          ),
        ),
        child: child!,
      ),
    );
    if (date == null || !mounted) return;

    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_occurredAt),
      builder: (context, child) => Theme(
        data: ThemeData.dark().copyWith(
          colorScheme: const ColorScheme.dark(
            primary: AppColors.drkRed,
            surface: AppColors.surface,
          ),
        ),
        child: child!,
      ),
    );
    if (!mounted) return;

    setState(() {
      _occurredAt = DateTime(
        date.year, date.month, date.day,
        time?.hour ?? _occurredAt.hour,
        time?.minute ?? _occurredAt.minute,
      );
    });
  }

  Future<void> _submit() async {
    final title = _titleController.text.trim();
    if (title.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Bitte eine kurze Bezeichnung angeben'),
          backgroundColor: AppColors.orange,
        ),
      );
      return;
    }

    setState(() => _saving = true);
    final api = context.read<AppState>().api;
    final result = await api.logDeployment(
      category: _category,
      title: title,
      description: _descController.text.trim().isEmpty ? null : _descController.text.trim(),
      occurredAt: _occurredAt,
      forcesCount: int.tryParse(_forcesController.text.trim()),
      severityRating: _severity,
    );

    if (!mounted) return;
    setState(() => _saving = false);

    if (result == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Einsatz konnte nicht gespeichert werden'),
          backgroundColor: AppColors.red,
        ),
      );
      return;
    }

    final wasPredicted = result['was_predicted'] as bool? ?? false;
    _titleController.clear();
    _descController.clear();
    _forcesController.clear();
    setState(() => _occurredAt = DateTime.now());
    await _loadRecent();

    if (!mounted) return;
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        icon: Icon(
          wasPredicted ? Icons.check_circle : Icons.school,
          color: wasPredicted ? AppColors.green : AppColors.orange,
          size: 36,
        ),
        title: Text(
          wasPredicted ? 'Einsatz war vorgewarnt' : 'Verpasste Warnung erfasst',
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 17),
          textAlign: TextAlign.center,
        ),
        content: Text(
          result['hinweis'] as String? ?? '',
          style: const TextStyle(color: AppColors.textSecondary, fontSize: 13, height: 1.45),
          textAlign: TextAlign.center,
        ),
        actions: [
          Center(
            child: TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Verstanden',
                  style: TextStyle(color: AppColors.drkRedAccent)),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Einsatz melden'), backgroundColor: AppColors.surface),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.orange.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.orange.withValues(alpha: 0.3)),
            ),
            child: const Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.lightbulb_outline, size: 16, color: AppColors.orange),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Melde hier auch Einsätze, vor denen das System NICHT gewarnt hat. '
                    'Genau daraus lernt es, künftig früher anzuschlagen.',
                    style: TextStyle(color: AppColors.orange, fontSize: 12, height: 1.4),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          _label('Kategorie'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: kRiskCategories.map((c) {
              final selected = _category == c.key;
              return GestureDetector(
                onTap: () => setState(() => _category = c.key),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: selected ? AppColors.drkRed : AppColors.surface,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                        color: selected ? AppColors.drkRed : AppColors.border),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(c.icon, size: 14,
                          color: selected ? Colors.white : AppColors.textSecondary),
                      const SizedBox(width: 5),
                      Text(c.label,
                          style: TextStyle(
                            color: selected ? Colors.white : AppColors.textSecondary,
                            fontSize: 12,
                            fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                          )),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 20),

          _label('Bezeichnung'),
          const SizedBox(height: 8),
          _field(_titleController, 'z.B. Kellerauspumpen Bergstraße'),
          const SizedBox(height: 16),

          _label('Zeitpunkt'),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: _pickDateTime,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                children: [
                  const Icon(Icons.schedule, size: 18, color: AppColors.textMuted),
                  const SizedBox(width: 10),
                  Text(
                    _formatDateTime(_occurredAt),
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
                  ),
                  const Spacer(),
                  const Icon(Icons.edit, size: 15, color: AppColors.textMuted),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          _label('Eingesetzte Kräfte (optional)'),
          const SizedBox(height: 8),
          _field(_forcesController, 'Anzahl', keyboardType: TextInputType.number),
          const SizedBox(height: 16),

          _label('Einsatzschwere'),
          const SizedBox(height: 8),
          Row(
            children: List.generate(5, (i) {
              final value = i + 1;
              final active = _severity >= value;
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _severity = value),
                  child: Container(
                    margin: EdgeInsets.only(right: i < 4 ? 6 : 0),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: active
                          ? scoreColor(value * 20).withValues(alpha: 0.2)
                          : AppColors.surface,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                          color: active ? scoreColor(value * 20) : AppColors.border),
                    ),
                    child: Text('$value',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: active ? scoreColor(value * 20) : AppColors.textMuted,
                          fontWeight: FontWeight.w600,
                        )),
                  ),
                ),
              );
            }),
          ),
          const SizedBox(height: 16),

          _label('Beschreibung (optional)'),
          const SizedBox(height: 8),
          _field(_descController, 'Was war die Lage?', maxLines: 3),
          const SizedBox(height: 24),

          SizedBox(
            height: 50,
            child: ElevatedButton.icon(
              onPressed: _saving ? null : _submit,
              icon: _saving
                  ? const SizedBox(
                      width: 18, height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.save),
              label: const Text('Einsatz speichern',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.drkRed,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ),
          const SizedBox(height: 28),

          if (_recent != null && _recent!.isNotEmpty) ...[
            _label('Zuletzt gemeldete Einsätze'),
            const SizedBox(height: 8),
            ..._recent!.take(10).map(_deploymentTile),
          ],
        ],
      ),
    );
  }

  Widget _deploymentTile(DeploymentData d) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Icon(
            d.wasPredicted ? Icons.check_circle : Icons.error_outline,
            size: 18,
            color: d.wasPredicted ? AppColors.green : AppColors.orange,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(d.title,
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                    maxLines: 1, overflow: TextOverflow.ellipsis),
                Text(
                  '${d.categoryLabel} · ${d.occurredAt != null ? _formatDateTime(DateTime.parse(d.occurredAt!).toLocal()) : ''}'
                  '${d.wasPredicted ? "" : " · nicht vorgewarnt"}',
                  style: TextStyle(
                    color: d.wasPredicted ? AppColors.textMuted : AppColors.orange,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatDateTime(DateTime dt) {
    return '${dt.day.toString().padLeft(2, '0')}.${dt.month.toString().padLeft(2, '0')}.${dt.year} '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }

  Widget _label(String text) => Text(text,
      style: const TextStyle(
          color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w600));

  Widget _field(
    TextEditingController controller,
    String hint, {
    TextInputType? keyboardType,
    int maxLines = 1,
  }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      maxLines: maxLines,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: AppColors.textDim, fontSize: 13),
        filled: true,
        fillColor: AppColors.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.drkRed),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
    );
  }
}
