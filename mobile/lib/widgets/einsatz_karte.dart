import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';

/// Farbe und Symbol der Einsatzerwartung.
///
/// Bewusst eine eigene Skala neben dem Gesamtrisiko: Ein hohes Risiko in einem
/// anderen Kreis bleibt hier grün, weil Troisdorf dafür nicht gezogen wird.
({Color color, IconData icon}) _stufenStil(String level) {
  switch (level) {
    case 'einsatz_wahrscheinlich':
      return (color: AppColors.drkRedLight, icon: Icons.notifications_active);
    case 'bereitstellung_wahrscheinlich':
      return (color: AppColors.orange, icon: Icons.pending_actions);
    case 'bereitstellung_moeglich':
      return (color: AppColors.yellow, icon: Icons.schedule);
    case 'beobachtung':
      return (color: AppColors.textSecondary, icon: Icons.visibility);
    default:
      return (color: AppColors.green, icon: Icons.check_circle_outline);
  }
}

/// Zeigt, was die Lage für die eigene Bereitschaft bedeutet — nicht wie
/// schlimm sie an sich ist.
class EinsatzKarte extends StatelessWidget {
  final DeploymentAssessment assessment;
  final VoidCallback? onTap;

  const EinsatzKarte({super.key, required this.assessment, this.onTap});

  @override
  Widget build(BuildContext context) {
    final stil = _stufenStil(assessment.level);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: stil.color.withValues(alpha: 0.10),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: stil.color.withValues(alpha: 0.35)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(stil.icon, color: stil.color, size: 22),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Einsatzerwartung Bereitschaft',
                        style: TextStyle(
                            color: AppColors.textMuted, fontSize: 11),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        assessment.label,
                        style: TextStyle(
                          color: stil.color,
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
                if (onTap != null)
                  Icon(Icons.chevron_right, color: stil.color, size: 20),
              ],
            ),
            // Evakuierung im Kerngebiet ist der eine Fall, bei dem keine
            // Abwägung nötig ist — das gehört ganz nach oben.
            if (assessment.hasEvacuation) ...[
              const SizedBox(height: 10),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: (assessment.isCoreEvacuation
                          ? AppColors.drkRed
                          : AppColors.orange)
                      .withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.groups,
                        color: assessment.isCoreEvacuation
                            ? AppColors.drkRedAccent
                            : AppColors.orangeLight,
                        size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        assessment.isCoreEvacuation
                            ? 'Hinweis auf Evakuierung in '
                                '${assessment.evacuationOrt} — Betreuung und '
                                'Verpflegung erfahrungsgemäß sicher'
                            : 'Hinweis auf Evakuierung in '
                                '${assessment.evacuationOrt} — direkte '
                                'Nachbarschaft, Einsatz möglich',
                        style: TextStyle(
                            color: assessment.isCoreEvacuation
                                ? AppColors.drkRedAccent
                                : AppColors.orangeLight,
                            fontSize: 11.5,
                            fontWeight: FontWeight.w500,
                            height: 1.35),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            if (assessment.description.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                assessment.description,
                style: const TextStyle(
                    color: AppColors.textSecondary, fontSize: 12, height: 1.4),
              ),
            ],
            if (assessment.components.isNotEmpty) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: assessment.components
                    .take(4)
                    .map((c) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppColors.surfaceLight,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            c,
                            style: const TextStyle(
                                color: AppColors.textSecondary, fontSize: 10),
                          ),
                        ))
                    .toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Ausführliche Begründung samt Belegstellen.
class EinsatzDetailSheet extends StatelessWidget {
  final DeploymentAssessment assessment;

  const EinsatzDetailSheet({super.key, required this.assessment});

  @override
  Widget build(BuildContext context) {
    final stil = _stufenStil(assessment.level);

    return Container(
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
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Icon(stil.icon, color: stil.color, size: 24),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    assessment.label,
                    style: TextStyle(
                        color: stil.color,
                        fontSize: 18,
                        fontWeight: FontWeight.w700),
                  ),
                ),
                Text(
                  '${assessment.value.round()}/100',
                  style: const TextStyle(
                      color: AppColors.textMuted, fontSize: 13),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              assessment.description,
              style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 13, height: 1.5),
            ),

            if (assessment.reasons.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text('Wie das zustande kommt',
                  style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              ...assessment.reasons.map((r) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Padding(
                          padding: EdgeInsets.only(top: 5, right: 8),
                          child: Icon(Icons.circle,
                              size: 5, color: AppColors.textMuted),
                        ),
                        Expanded(
                          child: Text(r,
                              style: const TextStyle(
                                  color: AppColors.textSecondary,
                                  fontSize: 12.5,
                                  height: 1.45)),
                        ),
                      ],
                    ),
                  )),
            ],

            if (assessment.components.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text('Voraussichtlich gebraucht',
                  style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: assessment.components
                    .map((c) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: AppColors.surfaceLight,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppColors.border),
                          ),
                          child: Text(c,
                              style: const TextStyle(
                                  color: AppColors.textSecondary,
                                  fontSize: 11)),
                        ))
                    .toList(),
              ),
            ],

            if (assessment.knowledge.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text('Grundlage',
                  style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              const Text(
                'Diese Einträge der Wissensdatenbank passen zur Lage.',
                style: TextStyle(color: AppColors.textMuted, fontSize: 11),
              ),
              const SizedBox(height: 8),
              ...assessment.knowledge.map((k) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          k.isOfficial ? Icons.verified_outlined : Icons.edit_note,
                          size: 14,
                          color: k.isOfficial
                              ? AppColors.green
                              : AppColors.purpleLight,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(k.title,
                                  style: const TextStyle(
                                      color: AppColors.textSecondary,
                                      fontSize: 12)),
                              if (k.source != null)
                                Text(k.source!,
                                    style: const TextStyle(
                                        color: AppColors.textDim,
                                        fontSize: 10)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  )),
            ],
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}
