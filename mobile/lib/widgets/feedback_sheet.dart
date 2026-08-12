import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';

/// Fragt nach einem Alarm ab, ob es tatsächlich zum Einsatz kam.
/// Diese Rückmeldung ist die einzige Quelle, aus der das System lernen kann.
Future<bool?> showFeedbackSheet(BuildContext context, AlertData alert) {
  return showModalBottomSheet<bool>(
    context: context,
    backgroundColor: AppColors.surface,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (_) => _FeedbackSheet(alert: alert),
  );
}

class _FeedbackSheet extends StatefulWidget {
  final AlertData alert;
  const _FeedbackSheet({required this.alert});

  @override
  State<_FeedbackSheet> createState() => _FeedbackSheetState();
}

class _FeedbackSheetState extends State<_FeedbackSheet> {
  FeedbackOutcome? _outcome;
  final _typeController = TextEditingController();
  final _forcesController = TextEditingController();
  final _notesController = TextEditingController();
  int _severity = 3;
  bool _saving = false;

  @override
  void dispose() {
    _typeController.dispose();
    _forcesController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  bool get _isDeployment => _outcome == FeedbackOutcome.einsatz;

  Color _outcomeColor(FeedbackOutcome o) {
    switch (o) {
      case FeedbackOutcome.einsatz:
        return AppColors.red;
      case FeedbackOutcome.vorsorge:
        return AppColors.orange;
      case FeedbackOutcome.keinEinsatz:
        return AppColors.green;
      case FeedbackOutcome.unklar:
        return AppColors.textMuted;
    }
  }

  IconData _outcomeIcon(FeedbackOutcome o) {
    switch (o) {
      case FeedbackOutcome.einsatz:
        return Icons.local_shipping;
      case FeedbackOutcome.vorsorge:
        return Icons.shield;
      case FeedbackOutcome.keinEinsatz:
        return Icons.check_circle_outline;
      case FeedbackOutcome.unklar:
        return Icons.help_outline;
    }
  }

  Future<void> _submit() async {
    if (_outcome == null) return;
    setState(() => _saving = true);

    final ok = await context.read<AppState>().submitFeedback(
          alertId: widget.alert.id,
          outcome: _outcome!,
          deploymentType:
              _typeController.text.trim().isEmpty ? null : _typeController.text.trim(),
          forcesCount: int.tryParse(_forcesController.text.trim()),
          severityRating: _isDeployment ? _severity : null,
          notes: _notesController.text.trim().isEmpty ? null : _notesController.text.trim(),
        );

    if (!mounted) return;
    setState(() => _saving = false);
    Navigator.of(context).pop(ok);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok
            ? 'Danke — das System lernt aus dieser Rückmeldung'
            : 'Rückmeldung konnte nicht gespeichert werden'),
        backgroundColor: ok ? AppColors.green : AppColors.red,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40, height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const Text(
              'Kam es zum Einsatz?',
              style: TextStyle(
                  color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              widget.alert.title,
              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),
            const Text(
              'Deine Antwort verbessert die Treffsicherheit künftiger Warnungen.',
              style: TextStyle(color: AppColors.textMuted, fontSize: 11, height: 1.4),
            ),
            const SizedBox(height: 16),

            ...FeedbackOutcome.values.map((o) {
              final selected = _outcome == o;
              final color = _outcomeColor(o);
              return GestureDetector(
                onTap: () => setState(() => _outcome = o),
                child: Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: selected ? color.withValues(alpha: 0.12) : AppColors.background,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: selected ? color : AppColors.border,
                      width: selected ? 1.5 : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(_outcomeIcon(o), size: 20,
                          color: selected ? color : AppColors.textMuted),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(o.label,
                                style: TextStyle(
                                  color: selected ? color : AppColors.textPrimary,
                                  fontSize: 14,
                                  fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                                )),
                            Text(o.description,
                                style: const TextStyle(
                                    color: AppColors.textMuted, fontSize: 11)),
                          ],
                        ),
                      ),
                      if (selected) Icon(Icons.check_circle, size: 18, color: color),
                    ],
                  ),
                ),
              );
            }),

            // Zusatzangaben nur bei echtem Einsatz — sonst nicht zumutbar
            if (_isDeployment) ...[
              const SizedBox(height: 8),
              const Text('Angaben zum Einsatz (optional)',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12)),
              const SizedBox(height: 8),
              _field(_typeController, 'Art des Einsatzes', 'z.B. Sandsackverbau, Betreuung'),
              const SizedBox(height: 8),
              _field(_forcesController, 'Eingesetzte Kräfte', 'Anzahl',
                  keyboardType: TextInputType.number),
              const SizedBox(height: 12),
              const Text('Einsatzschwere',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12)),
              const SizedBox(height: 6),
              Row(
                children: List.generate(5, (i) {
                  final value = i + 1;
                  final active = _severity >= value;
                  return Expanded(
                    child: GestureDetector(
                      onTap: () => setState(() => _severity = value),
                      child: Container(
                        margin: EdgeInsets.only(right: i < 4 ? 6 : 0),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        decoration: BoxDecoration(
                          color: active
                              ? scoreColor(value * 20).withValues(alpha: 0.2)
                              : AppColors.background,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: active ? scoreColor(value * 20) : AppColors.border,
                          ),
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
            ],

            if (_outcome != null) ...[
              const SizedBox(height: 12),
              _field(_notesController, 'Notiz', 'Was war entscheidend?', maxLines: 2),
            ],

            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: TextButton(
                    onPressed: _saving ? null : () => Navigator.of(context).pop(null),
                    child: const Text('Später',
                        style: TextStyle(color: AppColors.textMuted)),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: ElevatedButton(
                    onPressed: (_outcome == null || _saving) ? null : _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.drkRed,
                      disabledBackgroundColor: AppColors.border,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _saving
                        ? const SizedBox(
                            width: 18, height: 18,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white))
                        : const Text('Rückmeldung senden',
                            style: TextStyle(
                                color: Colors.white, fontWeight: FontWeight.w600)),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label,
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
        labelText: label,
        labelStyle: const TextStyle(color: AppColors.textMuted, fontSize: 12),
        hintText: hint,
        hintStyle: const TextStyle(color: AppColors.textDim, fontSize: 13),
        filled: true,
        fillColor: AppColors.background,
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
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      ),
    );
  }
}
