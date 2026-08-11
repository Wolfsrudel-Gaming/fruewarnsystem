import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../services/app_state.dart';
import '../widgets/alert_card.dart';

class AlarmeScreen extends StatefulWidget {
  const AlarmeScreen({super.key});

  @override
  State<AlarmeScreen> createState() => _AlarmeScreenState();
}

class _AlarmeScreenState extends State<AlarmeScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          color: AppColors.surface,
          child: TabBar(
            controller: _tabController,
            indicatorColor: AppColors.drkRed,
            labelColor: AppColors.drkRedLight,
            unselectedLabelColor: AppColors.textMuted,
            tabs: const [
              Tab(text: 'Aktiv'),
              Tab(text: 'Quittiert'),
              Tab(text: 'Historie'),
            ],
          ),
        ),
        Expanded(
          child: Consumer<AppState>(
            builder: (context, state, _) {
              return TabBarView(
                controller: _tabController,
                children: [
                  _buildAlertList(state, state.alerts.where((a) => !a.acknowledged).toList()),
                  _buildAlertList(state, state.alerts.where((a) => a.acknowledged).toList()),
                  _buildAlertList(state, state.alerts),
                ],
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildAlertList(AppState state, List<dynamic> alerts) {
    if (alerts.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: const [
            Icon(Icons.check_circle_outline, color: AppColors.green, size: 48),
            SizedBox(height: 12),
            Text('Keine Alarme', style: TextStyle(color: AppColors.textSecondary)),
          ],
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
            onAcknowledge: alert.acknowledged ? null : () => state.acknowledgeAlert(alert.id),
          );
        },
      ),
    );
  }
}
