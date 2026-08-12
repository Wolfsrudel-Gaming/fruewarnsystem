import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';

/// Relevante Lokalnachrichten (RSS + KI-Relevanzbewertung)
class NewsScreen extends StatefulWidget {
  const NewsScreen({super.key});

  @override
  State<NewsScreen> createState() => _NewsScreenState();
}

class _NewsScreenState extends State<NewsScreen> {
  List<NewsItemData>? _items;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<AppState>().api;
    final items = await api.fetchNews();
    if (mounted) setState(() => _items = items);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Nachrichten'), backgroundColor: AppColors.surface),
      body: _items == null
          ? const Center(child: CircularProgressIndicator(color: AppColors.drkRed))
          : _items!.isEmpty
              ? const Center(
                  child: Text('Keine relevanten Nachrichten',
                      style: TextStyle(color: AppColors.textMuted)),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  color: AppColors.drkRed,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _items!.length,
                    itemBuilder: (context, i) => _newsCard(_items![i]),
                  ),
                ),
    );
  }

  Widget _newsCard(NewsItemData n) {
    final relevance = ((n.relevanceScore ?? 0) * 100).round();
    return GestureDetector(
      onTap: n.url == null
          ? null
          : () => launchUrl(Uri.parse(n.url!), mode: LaunchMode.externalApplication),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(n.title,
                      style: const TextStyle(
                          color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w600, height: 1.35)),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                  decoration: BoxDecoration(
                    color: scoreColor(relevance).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text('$relevance%',
                      style: TextStyle(
                          color: scoreColor(relevance), fontSize: 11, fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            if (n.summary != null && n.summary!.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(n.summary!,
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 12, height: 1.4),
                  maxLines: 3, overflow: TextOverflow.ellipsis),
            ],
            const SizedBox(height: 8),
            Row(
              children: [
                if (n.source != null)
                  Text(n.source!,
                      style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
                if (n.category != null) ...[
                  const Text(' · ', style: TextStyle(color: AppColors.textMuted, fontSize: 11)),
                  Text(n.category!,
                      style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
                ],
                const Spacer(),
                if (n.url != null)
                  const Icon(Icons.open_in_new, size: 13, color: AppColors.textMuted),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
