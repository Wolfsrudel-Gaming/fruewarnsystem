import 'package:flutter_test/flutter_test.dart';

import 'package:fruewarnsystem/services/alarm_policy.dart';

/// Tests der Alarmierungsregel.
///
/// Das ist die Stelle, an der ein Fehler am teuersten ist: Zu still bedeutet
/// einen verschlafenen Einsatz, zu laut einen Weckruf um drei Uhr nachts ohne
/// Anlass. Beides untergräbt das Vertrauen in die App.
void main() {
  const ohneRuhezeit = RuhezeitEinstellung(aktiv: false);
  const nachtruhe = RuhezeitEinstellung(
    aktiv: true,
    startMinute: 22 * 60,
    endeMinute: 6 * 60,
    weckStufe: 'einsatz_wahrscheinlich',
  );

  final tags = DateTime(2026, 8, 20, 14, 0);
  final nachts = DateTime(2026, 8, 20, 3, 0);

  AlarmStaerke wechsel(String? alt, String neu,
      {DateTime? zeit, RuhezeitEinstellung? rz}) {
    return bewerteStufenwechsel(
      alteStufe: alt,
      neueStufe: neu,
      jetzt: zeit ?? tags,
      ruhezeit: rz ?? ohneRuhezeit,
    );
  }

  group('Ruhezeit-Fenster', () {
    test('erkennt Zeiten über Mitternacht hinweg', () {
      // Der Normalfall: Beginn liegt später am Tag als das Ende.
      expect(nachtruhe.giltZu(DateTime(2026, 8, 20, 23, 30)), isTrue);
      expect(nachtruhe.giltZu(DateTime(2026, 8, 20, 3, 0)), isTrue);
      expect(nachtruhe.giltZu(DateTime(2026, 8, 20, 5, 59)), isTrue);
      expect(nachtruhe.giltZu(DateTime(2026, 8, 20, 6, 0)), isFalse);
      expect(nachtruhe.giltZu(DateTime(2026, 8, 20, 14, 0)), isFalse);
    });

    test('erkennt Zeiten innerhalb eines Tages', () {
      const mittagsruhe = RuhezeitEinstellung(
          aktiv: true, startMinute: 13 * 60, endeMinute: 15 * 60);
      expect(mittagsruhe.giltZu(DateTime(2026, 8, 20, 14, 0)), isTrue);
      expect(mittagsruhe.giltZu(DateTime(2026, 8, 20, 12, 0)), isFalse);
      expect(mittagsruhe.giltZu(DateTime(2026, 8, 20, 23, 0)), isFalse);
    });

    test('gilt nie, wenn sie abgeschaltet ist', () {
      expect(ohneRuhezeit.giltZu(DateTime(2026, 8, 20, 3, 0)), isFalse);
    });

    test('gleicher Beginn und gleiches Ende gilt als abgeschaltet', () {
      // Sonst wäre unklar, ob null oder 24 Stunden gemeint sind.
      const entartet = RuhezeitEinstellung(
          aktiv: true, startMinute: 60, endeMinute: 60);
      expect(entartet.giltZu(DateTime(2026, 8, 20, 1, 0)), isFalse);
    });
  });

  group('Weckruf', () {
    test('Einsatz wahrscheinlich weckt am Tag', () {
      expect(wechsel('beobachtung', 'einsatz_wahrscheinlich'),
          AlarmStaerke.weckruf);
    });

    test('Einsatz wahrscheinlich weckt auch in der Ruhezeit', () {
      // Standardmäßig steht die Weckschwelle genau hier — ein Einsatz kommt
      // auch um drei Uhr.
      expect(
        wechsel('ruhe', 'einsatz_wahrscheinlich',
            zeit: nachts, rz: nachtruhe),
        AlarmStaerke.weckruf,
      );
    });

    test('höhere Weckschwelle unterdrückt den Weckruf nachts nicht', () {
      // Es gibt keine Stufe über "Einsatz wahrscheinlich" — die Regel darf
      // hier nicht ins Leere laufen.
      const strikt =
          RuhezeitEinstellung(aktiv: true, weckStufe: 'einsatz_wahrscheinlich');
      expect(
        wechsel('ruhe', 'einsatz_wahrscheinlich', zeit: nachts, rz: strikt),
        AlarmStaerke.weckruf,
      );
    });

    test('Bereitstellung weckt nachts nicht bei Standardeinstellung', () {
      expect(
        wechsel('ruhe', 'bereitstellung_wahrscheinlich',
            zeit: nachts, rz: nachtruhe),
        AlarmStaerke.still,
      );
    });

    test('Bereitstellung meldet sich tagsüber', () {
      expect(wechsel('ruhe', 'bereitstellung_wahrscheinlich'),
          AlarmStaerke.meldung);
    });

    test('niedrigere Weckschwelle lässt Bereitstellung nachts durch', () {
      const frueh = RuhezeitEinstellung(
          aktiv: true, weckStufe: 'bereitstellung_wahrscheinlich');
      expect(
        wechsel('ruhe', 'bereitstellung_wahrscheinlich',
            zeit: nachts, rz: frueh),
        AlarmStaerke.meldung,
      );
    });
  });

  group('Unveränderte Lage', () {
    test('meldet sich nicht erneut', () {
      // Ohne diese Regel meldete sich die App bei jedem Abruf — genau der
      // Fehler, der beim Server schon einmal 288 Duplikate erzeugt hat.
      expect(wechsel('bereitstellung_moeglich', 'bereitstellung_moeglich'),
          AlarmStaerke.keine);
    });

    test('gilt auch für die höchste Stufe', () {
      expect(wechsel('einsatz_wahrscheinlich', 'einsatz_wahrscheinlich'),
          AlarmStaerke.keine);
    });
  });

  group('Entwarnung', () {
    test('deutliche Entspannung wird gemeldet', () {
      // Eine Entwarnung ist auch eine Information — man weiß, dass man
      // wieder abschalten kann.
      expect(wechsel('einsatz_wahrscheinlich', 'beobachtung'),
          AlarmStaerke.meldung);
    });

    test('kleine Entspannung bleibt still', () {
      expect(
        wechsel('einsatz_wahrscheinlich', 'bereitstellung_wahrscheinlich'),
        AlarmStaerke.still,
      );
    });

    test('weckt nie, auch nicht am Tag', () {
      for (final ziel in ['ruhe', 'beobachtung', 'bereitstellung_moeglich']) {
        expect(wechsel('einsatz_wahrscheinlich', ziel),
            isNot(AlarmStaerke.weckruf));
      }
    });

    test('Text nennt die Entspannung beim Namen', () {
      final t = stufenwechselText(
        alteStufe: 'einsatz_wahrscheinlich',
        neueStufe: 'ruhe',
        neuesLabel: 'Ruhe',
      );
      expect(t.titel, contains('entspannt'));
      expect(t.text, contains('Ruhe'));
    });
  });

  group('Erster Abruf', () {
    test('unbekannte Vorstufe zählt als Ruhe', () {
      // Beim Start gibt es keinen Vorzustand. Ein Sprung auf "Einsatz
      // wahrscheinlich" muss trotzdem wecken.
      expect(wechsel(null, 'einsatz_wahrscheinlich'), AlarmStaerke.weckruf);
      expect(wechsel(null, 'ruhe'), AlarmStaerke.keine);
    });
  });

  group('Rangfolge', () {
    test('ist lückenlos und aufsteigend', () {
      const reihe = [
        'ruhe',
        'beobachtung',
        'bereitstellung_moeglich',
        'bereitstellung_wahrscheinlich',
        'einsatz_wahrscheinlich',
      ];
      for (var i = 1; i < reihe.length; i++) {
        expect(stufenRang(reihe[i]), greaterThan(stufenRang(reihe[i - 1])));
      }
    });

    test('unbekannte Stufe zählt als niedrigste', () {
      expect(stufenRang('quatsch'), 0);
      expect(stufenRang(null), 0);
    });
  });

  group('Meldungstext', () {
    test('nennt bei Verschärfung die neue Stufe als Titel', () {
      final t = stufenwechselText(
        alteStufe: 'beobachtung',
        neueStufe: 'einsatz_wahrscheinlich',
        neuesLabel: 'Einsatz wahrscheinlich',
        anlass: 'Fliegerbombe in Siegburg',
      );
      expect(t.titel, 'Einsatz wahrscheinlich');
      expect(t.text, contains('Siegburg'));
    });

    test('kommt ohne Anlass aus', () {
      final t = stufenwechselText(
        alteStufe: 'ruhe',
        neueStufe: 'bereitstellung_moeglich',
        neuesLabel: 'Bereitstellung möglich',
      );
      expect(t.text.isNotEmpty, isTrue);
    });
  });
}
