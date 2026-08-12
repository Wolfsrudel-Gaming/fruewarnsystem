import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'theme/app_theme.dart';
import 'services/api_service.dart';
import 'services/app_state.dart';
import 'services/background_service.dart';
import 'services/notification_service.dart';
import 'screens/lagebild_screen.dart';
import 'screens/alarme_screen.dart';
import 'screens/lagekarte_screen.dart';
import 'screens/ki_bericht_screen.dart';
import 'screens/mehr_screen.dart';
import 'screens/kritischer_alarm_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: AppColors.surface,
  ));

  final prefs = await SharedPreferences.getInstance();
  final serverUrl = prefs.getString('server_url') ?? 'http://10.0.2.2:8000';

  await NotificationService.initialize();
  await NotificationService.requestPermissions();
  await BackgroundAlarmService.initialize();

  runApp(FruewarnsystemApp(serverUrl: serverUrl));
}

class FruewarnsystemApp extends StatelessWidget {
  final String serverUrl;
  const FruewarnsystemApp({super.key, required this.serverUrl});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AppState(api: ApiService(baseUrl: serverUrl)),
      child: MaterialApp(
        title: 'DRK Frühwarnsystem',
        theme: appTheme(),
        debugShowCheckedModeBanner: false,
        home: const MainShell(),
      ),
    );
  }
}

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;
  AppState? _appState;

  static const _screens = <Widget>[
    LagebildScreen(),
    AlarmeScreen(),
    LagekarteScreen(),
    KiBerichtScreen(),
    MehrScreen(),
  ];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = context.read<AppState>();
    if (_appState != state) {
      _appState?.removeListener(_checkCriticalAlert);
      _appState = state;
      state.addListener(_checkCriticalAlert);
    }
  }

  @override
  void dispose() {
    _appState?.removeListener(_checkCriticalAlert);
    super.dispose();
  }

  /// Bei kritischem Alarm (Score >= 80) Vollbild-Weckruf anzeigen
  void _checkCriticalAlert() {
    final state = _appState;
    final alert = state?.pendingCriticalAlert;
    if (state == null || alert == null || !mounted) return;
    state.clearCriticalAlert();
    Navigator.of(context).push(MaterialPageRoute(
      fullscreenDialog: true,
      builder: (_) => KritischerAlarmScreen(
        alert: alert,
        onAcknowledge: () => state.acknowledgeAlert(alert.id),
      ),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                color: AppColors.drkRed,
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Center(
                child: Text(
                  'DRK',
                  style: TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                ),
              ),
            ),
            const SizedBox(width: 10),
            const Text(
              'Frühwarnsystem',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
            ),
          ],
        ),
        actions: [
          Consumer<AppState>(
            builder: (context, state, _) {
              final activeCount = state.alerts.where((a) => !a.acknowledged).length;
              return Stack(
                children: [
                  IconButton(
                    icon: const Icon(Icons.notifications_outlined),
                    onPressed: () => setState(() => _currentIndex = 1),
                  ),
                  if (activeCount > 0)
                    Positioned(
                      right: 8,
                      top: 8,
                      child: Container(
                        width: 16, height: 16,
                        decoration: const BoxDecoration(
                          color: AppColors.drkRed,
                          shape: BoxShape.circle,
                        ),
                        child: Center(
                          child: Text(
                            activeCount > 9 ? '9+' : '$activeCount',
                            style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold),
                          ),
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: AppColors.border, width: 0.5)),
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (i) => setState(() => _currentIndex = i),
          type: BottomNavigationBarType.fixed,
          backgroundColor: AppColors.surface,
          selectedItemColor: AppColors.drkRedLight,
          unselectedItemColor: AppColors.textMuted,
          selectedFontSize: 11,
          unselectedFontSize: 11,
          items: const [
            BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), activeIcon: Icon(Icons.dashboard), label: 'Lage'),
            BottomNavigationBarItem(icon: Icon(Icons.warning_amber_outlined), activeIcon: Icon(Icons.warning_amber), label: 'Alarme'),
            BottomNavigationBarItem(icon: Icon(Icons.map_outlined), activeIcon: Icon(Icons.map), label: 'Karte'),
            BottomNavigationBarItem(icon: Icon(Icons.auto_awesome_outlined), activeIcon: Icon(Icons.auto_awesome), label: 'Bericht'),
            BottomNavigationBarItem(icon: Icon(Icons.more_horiz), activeIcon: Icon(Icons.more_horiz), label: 'Mehr'),
          ],
        ),
      ),
    );
  }
}
