import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../services/app_state.dart';

class EinstellungenScreen extends StatefulWidget {
  final ApiService api;
  const EinstellungenScreen({super.key, required this.api});

  @override
  State<EinstellungenScreen> createState() => _EinstellungenScreenState();
}

class _EinstellungenScreenState extends State<EinstellungenScreen> {
  bool _pushEnabled = true;
  bool _ntfyEnabled = false;
  bool _telegramEnabled = false;
  bool _smsEnabled = false;
  bool _voiceEnabled = false;
  String _serverUrl = '';
  final _urlController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _serverUrl = widget.api.baseUrl;
    _urlController.text = _serverUrl;
    _loadPrefs();
  }

  Future<void> _loadPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _pushEnabled = prefs.getBool('push_enabled') ?? true;
      _ntfyEnabled = prefs.getBool('ntfy_enabled') ?? false;
      _telegramEnabled = prefs.getBool('telegram_enabled') ?? false;
      _smsEnabled = prefs.getBool('sms_enabled') ?? false;
      _voiceEnabled = prefs.getBool('voice_enabled') ?? false;
      final saved = prefs.getString('server_url');
      if (saved != null && saved.isNotEmpty) {
        _serverUrl = saved;
        _urlController.text = saved;
        widget.api.baseUrl = saved;
      }
    });
  }

  Future<void> _saveToggle(String key, bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(key, value);
  }

  Future<void> _saveUrl() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', url);
    widget.api.baseUrl = url;
    setState(() => _serverUrl = url);
    if (mounted) {
      // Daten und WebSocket sofort mit der neuen URL neu verbinden
      context.read<AppState>().reconnect();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Server-URL gespeichert, verbinde neu…'), backgroundColor: AppColors.green),
      );
    }
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Einstellungen'), backgroundColor: AppColors.surface),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _sectionTitle('Benachrichtigungskanäle'),
          const SizedBox(height: 8),
          _buildToggleSection(),
          const SizedBox(height: 24),
          _sectionTitle('Server-Verbindung'),
          const SizedBox(height: 8),
          _buildServerSection(),
          const SizedBox(height: 24),
          _sectionTitle('System'),
          const SizedBox(height: 8),
          _buildSystemInfo(),
        ],
      ),
    );
  }

  Widget _sectionTitle(String text) {
    return Text(
      text,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
    );
  }

  Widget _buildToggleSection() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          _toggle('Push (FCM)', Icons.notifications, _pushEnabled, (v) {
            setState(() => _pushEnabled = v);
            _saveToggle('push_enabled', v);
          }),
          _divider(),
          _toggle('ntfy', Icons.campaign, _ntfyEnabled, (v) {
            setState(() => _ntfyEnabled = v);
            _saveToggle('ntfy_enabled', v);
          }),
          _divider(),
          _toggle('Telegram', Icons.send, _telegramEnabled, (v) {
            setState(() => _telegramEnabled = v);
            _saveToggle('telegram_enabled', v);
          }),
          _divider(),
          _toggle('SMS', Icons.sms, _smsEnabled, (v) {
            setState(() => _smsEnabled = v);
            _saveToggle('sms_enabled', v);
          }),
          _divider(),
          _toggle('Sprachanruf', Icons.phone, _voiceEnabled, (v) {
            setState(() => _voiceEnabled = v);
            _saveToggle('voice_enabled', v);
          }),
        ],
      ),
    );
  }

  Widget _toggle(String label, IconData icon, bool value, ValueChanged<bool> onChanged) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppColors.textMuted),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: const TextStyle(color: AppColors.textPrimary, fontSize: 14))),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppColors.drkRed,
          ),
        ],
      ),
    );
  }

  Widget _divider() => const Divider(color: AppColors.border, height: 1, indent: 46);

  Widget _buildServerSection() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Server URL', style: TextStyle(color: AppColors.textMuted, fontSize: 12)),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _urlController,
                  style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
                  decoration: InputDecoration(
                    hintText: 'http://192.168.1.100:8000',
                    hintStyle: const TextStyle(color: AppColors.textDim),
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
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: _saveUrl,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.drkRed,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                child: const Text('Speichern'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSystemInfo() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          _infoRow('App-Version', '1.0.0'),
          const SizedBox(height: 8),
          _infoRow('Plattform', 'Android'),
          const SizedBox(height: 8),
          _infoRow('Server', _serverUrl),
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
        Flexible(
          child: Text(
            value,
            style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}
