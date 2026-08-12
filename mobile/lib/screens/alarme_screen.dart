import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';
import '../widgets/alert_card.dart';
import '../widgets/feedback_sheet.dart';

class AlarmeScreen extends StatefulWidget {
  const AlarmeScreen({super.key});

  @override
  State<AlarmeScreen> createState() => _AlarmeScreenState();
}

class _AlarmeScreenState extends State<AlarmeScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, state, _) {
        final pendingIds = state.pendingFeedback.map((a) => a.id).toSet();

        return Column(
          children: [
            Container(
              color: AppColors.surface,
              child: TabBar(
                controller: _tabController,
                indicatorColor: AppColors.drkRed,
                labelColor: AppColors.drkRedLight,
                unselectedLabelColor: AppColors.textMuted,
                labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                unselectedLabelStyle: const TextStyle(fontSize: 13),
                tabs: [
                  const Tab(text: 'Aktiv'),
                  Tab(
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Text('Rückmeldung'),
                        if (pendingIds.isNotEmpty) ...[
                          const SizedBox(width: 5),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 5, vertical: 1),
                            decoration: BoxDecoration(
                              color: AppColors.orange,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text('${pendingIds.length}',
                                style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold)),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const Tab(text: 'Quittiert'),
                  const Tab(text: 'Alle'),
                ],
              ),
            ),
            Expanded(
              child: TabBarView(
                controller: _tabController,
                children: [
                  _alertList(
                    state,
                    state.alerts.where((a) => !a.acknowledged).toList(),
                    pendingIds,
                    emptyIcon: Icons.check_circle_outline,
                    emptyText: 'Keine aktiven Alarme',
                  ),
                  _alertList(
                    state,
                    state.pendingFeedback,
                    pendingIds,
                    emptyIcon: Icons.task_alt,
                    emptyText: 'Alle Alarme bewertet',
                    emptyHint:
                        'Rückmeldungen machen das System mit der Zeit treffsicherer.',
                  ),
                  _alertList(
                    state,
                    state.alerts.where((a) => a.acknowledged).toList(),
                    pendingIds,
                    emptyIcon: Icons.inbox,
                    emptyText: 'Nichts quittiert',
                  ),
                  _alertList(
                    state,
                    state.alerts,
                    pendingIds,
                    emptyIcon: Icons.inbox,
                    emptyText: 'Keine Alarme',
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _alertList(
    AppState state,
    List<AlertData> alerts,
    Set<int> pendingIds, {
    required IconData emptyIcon,
    required String emptyText,
    String? emptyHint,
  }) {
    if (alerts.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 40),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(emptyIcon, color: AppColors.green, size: 48),
              const SizedBox(height: 12),
              Text(emptyText,
                  style: const TextStyle(color: AppColors.textSecondary)),
              if (emptyHint != null) ...[
                const SizedBox(height: 6),
                Text(emptyHint,
                    style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
                    textAlign: TextAlign.center),
              ],
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: state.refreshAll,
      color: AppColors.drkRed,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: alerts.length,
        itemBuilder: (context, i) {
          final alert = alerts[i];
          return AlertCard(
            alert: alert,
            onAcknowledge:
                alert.acknowledged ? null : () => state.acknowledgeAlert(alert.id),
            onFeedback: pendingIds.contains(alert.id)
                ? () => showFeedbackSheet(context, alert)
                : null,
          );
        },
      ),
    );
  }
}
