import 'package:flutter/material.dart';

/// Zentrale Registry der Risiko-Kategorien.
/// Die Keys entsprechen exakt dem AlertCategory-Enum des Backends.
class RiskCategory {
  final String key;
  final String label;
  final IconData icon;
  final String description;

  const RiskCategory(this.key, this.label, this.icon, this.description);
}

const List<RiskCategory> kRiskCategories = [
  RiskCategory('water', 'Hochwasser', Icons.water, 'Pegelstände Rhein, Sieg, Agger'),
  RiskCategory('weather', 'Wetter', Icons.thunderstorm, 'DWD-Warnungen und Vorhersage'),
  RiskCategory('fire', 'Waldbrand', Icons.local_fire_department, 'Gefahrenindex und Satelliten-Hotspots'),
  RiskCategory('official_warning', 'Behördenwarnung', Icons.campaign, 'NINA, Katwarn, MoWaS'),
  RiskCategory('traffic', 'Verkehr', Icons.traffic, 'Unfälle und Sperrungen'),
  RiskCategory('air_quality', 'Luftqualität', Icons.air, 'Feinstaub, Ozon, NO₂'),
  RiskCategory('seismic', 'Erdbeben', Icons.landslide, 'Seismische Aktivität in der Region'),
  RiskCategory('radiation', 'Strahlung', Icons.flare, 'BfS Gamma-Ortsdosisleistung'),
  RiskCategory('power', 'Stromnetz', Icons.bolt, 'Netzbelastung SMARD'),
  RiskCategory('health', 'Gesundheit', Icons.local_hospital, 'DIVI Intensivbetten-Auslastung'),
  RiskCategory('news', 'Nachrichten', Icons.newspaper, 'Relevante Lokalmeldungen'),
  RiskCategory('events', 'Veranstaltungen', Icons.event, 'Großveranstaltungen mit Risiko'),
  RiskCategory('shipping', 'Schifffahrt', Icons.directions_boat, 'ELWIS Rhein-Warnungen'),
];

RiskCategory categoryByKey(String key) {
  return kRiskCategories.firstWhere(
    (c) => c.key == key,
    orElse: () => RiskCategory(key, key, Icons.category, ''),
  );
}
