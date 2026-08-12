import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';

/// KI-Lagebericht — wird vom Backend generiert (lokales LLM via Ollama,
/// bei Nichtverfügbarkeit strukturierter Fallback aus Live-Daten).
class KiBerichtScreen extends StatefulWidget {
  const KiBerichtScreen({super.key});

  @override
  State<KiBerichtScreen> createState() => _KiBerichtScreenState();
}

class _KiBerichtScreenState extends State<KiBerichtScreen>
    with AutomaticKeepAliveClientMixin {
  SituationReport? _report;
  bool _loading = false;
  String? _error;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    final api = context.read<AppState>().api;
    final report = await api.fetchReport();
    if (!mounted) return;
    setState(() {
      _loading = false;
      if (report != null) {
        _report = report;
      } else {
        _error = 'Bericht konnte nicht geladen werden';
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.auto_awesome, color: AppColors.purple, size: 20),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'KI-Lagebericht',
                      style: TextStyle(
                          color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: (_report?.llmGenerated ?? false)
                          ? AppColors.purple.withValues(alpha: 0.15)
                          : AppColors.border,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      (_report?.llmGenerated ?? false) ? 'LLM · lokal' : 'Regelbasiert',
                      style: TextStyle(
                        color: (_report?.llmGenerated ?? false)
                            ? AppColors.purple
                            : AppColors.textMuted,
                        fontSize: 10,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (_loading && _report == null)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 40),
                  child: Center(
                    child: Column(
                      children: [
                        CircularProgressIndicator(color: AppColors.purple),
                        SizedBox(height: 12),
                        Text('Bericht wird generiert…',
                            style: TextStyle(color: AppColors.textMuted, fontSize: 12)),
                      ],
                    ),
                  ),
                )
              else if (_error != null && _report == null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 24),
                  child: Center(
                    child: Text(_error!,
                        style: const TextStyle(color: AppColors.textSecondary)),
                  ),
                )
              else if (_report != null)
                _renderReport(_report!.report),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _loading ? null : _load,
                icon: _loading
                    ? const SizedBox(
                        width: 16, height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.drkRed))
                    : const Icon(Icons.refresh, size: 16),
                label: const Text('Neu generieren'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.textSecondary,
                  side: const BorderSide(color: AppColors.border),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _report == null
                    ? null
                    : () {
                        Clipboard.setData(ClipboardData(text: _report!.report));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                              content: Text('Bericht kopiert'),
                              backgroundColor: AppColors.green),
                        );
                      },
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Kopieren'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.textSecondary,
                  side: const BorderSide(color: AppColors.border),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (_report != null)
          Center(
            child: Text(
              'Erstellt: ${_formatTime(_report!.generatedAt)}',
              style: const TextStyle(color: AppColors.textDim, fontSize: 11),
            ),
          ),
      ],
    );
  }

  String _formatTime(String iso) {
    final dt = DateTime.tryParse(iso)?.toLocal();
    if (dt == null) return iso;
    return '${dt.day.toString().padLeft(2, '0')}.${dt.month.toString().padLeft(2, '0')}. '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }

  /// Einfaches Markdown-Rendering: #-Überschriften fett, Listen eingerückt
  Widget _renderReport(String text) {
    final lines = text.split('\n');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: lines.map((line) {
        final trimmed = line.trimLeft();
        if (trimmed.startsWith('## ')) {
          return Padding(
            padding: const EdgeInsets.only(top: 12, bottom: 4),
            child: Text(trimmed.substring(3),
                style: const TextStyle(
                    color: AppColors.drkRedLight, fontSize: 14, fontWeight: FontWeight.w700)),
          );
        }
        if (trimmed.startsWith('# ')) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(trimmed.substring(2),
                style: const TextStyle(
                    color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w700)),
          );
        }
        if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
          return Padding(
            padding: const EdgeInsets.only(left: 8, bottom: 3),
            child: Text(trimmed,
                style: const TextStyle(
                    color: AppColors.textSecondary, fontSize: 13, height: 1.45)),
          );
        }
        if (trimmed.isEmpty) return const SizedBox(height: 6);
        return Padding(
          padding: const EdgeInsets.only(bottom: 3),
          child: Text(line,
              style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 13, height: 1.45)),
        );
      }).toList(),
    );
  }
}
