// iOS 시계 앱의 스톱워치 화면을 옮긴 위젯.
// 랩 기록 · 가장 짧은 랩(초록) · 가장 긴 랩(빨강) 표시를 포함한다.

import 'dart:async';

import 'package:flutter/material.dart';

/// Duration → "01:09.44" (분:초.1/100초)
String formatLapTime(Duration d) {
  final minutes = d.inMinutes.toString().padLeft(2, '0');
  final seconds = (d.inSeconds % 60).toString().padLeft(2, '0');
  final hundredths = (d.inMilliseconds % 1000 ~/ 10).toString().padLeft(2, '0');
  return '$minutes:$seconds.$hundredths';
}

class StopwatchPage extends StatefulWidget {
  const StopwatchPage({super.key});

  @override
  State<StopwatchPage> createState() => _StopwatchPageState();
}

class _StopwatchPageState extends State<StopwatchPage> {
  // 시간은 Stopwatch가 재고, 타이머는 화면을 다시 그리기만 한다.
  final _stopwatch = Stopwatch();
  Timer? _ticker;

  /// 완료된 랩들의 구간 시간(기록순).
  final _laps = <Duration>[];

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  Duration get _elapsed => _stopwatch.elapsed;

  /// 진행 중인 랩 = 전체 경과 - 이미 기록한 랩들의 합
  Duration get _currentLap =>
      _elapsed - _laps.fold(Duration.zero, (sum, lap) => sum + lap);

  void _toggle() {
    setState(() {
      if (_stopwatch.isRunning) {
        _stopwatch.stop();
        _ticker?.cancel();
      } else {
        _stopwatch.start();
        _ticker = Timer.periodic(
          const Duration(milliseconds: 33),
          (_) => setState(() {}),
        );
      }
    });
  }

  void _lapOrReset() {
    setState(() {
      if (_stopwatch.isRunning) {
        _laps.add(_currentLap);
      } else {
        _ticker?.cancel();
        _stopwatch.reset();
        _laps.clear();
      }
    });
  }

  /// 색을 칠하는 기준은 **완료된 랩**뿐이다. 진행 중인 랩은 아직 확정이 아니고,
  /// 랩이 하나뿐이면 최장·최단이 같은 값이라 색을 칠하지 않는다.
  ({Duration? shortest, Duration? longest}) get _extremes {
    if (_laps.length < 2) return (shortest: null, longest: null);
    final sorted = [..._laps]..sort();
    return (shortest: sorted.first, longest: sorted.last);
  }

  @override
  Widget build(BuildContext context) {
    final extremes = _extremes;
    final running = _stopwatch.isRunning;
    final idle = !running && _elapsed == Duration.zero;

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(),
            Text(
              formatLapTime(_elapsed),
              style: const TextStyle(
                fontSize: 72,
                fontWeight: FontWeight.w200,
                color: Colors.white,
                fontFeatures: [FontFeature.tabularFigures()],
              ),
            ),
            const Spacer(),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _RoundButton(
                    label: running ? '랩' : '재설정',
                    color: Colors.white,
                    background: const Color(0xFF333333),
                    // 시작 전에는 누를 것이 없다.
                    onPressed: idle ? null : _lapOrReset,
                  ),
                  _RoundButton(
                    label: running ? '중단' : '시작',
                    color: running
                        ? const Color(0xFFEB4B3A)
                        : const Color(0xFF30D158),
                    background: running
                        ? const Color(0xFF3A1A17)
                        : const Color(0xFF0B2E17),
                    onPressed: _toggle,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
            Expanded(
              child: _LapList(
                laps: _laps,
                currentLap: _currentLap,
                showCurrent: !idle,
                shortest: extremes.shortest,
                longest: extremes.longest,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({
    required this.label,
    required this.color,
    required this.background,
    required this.onPressed,
  });

  final String label;
  final Color color;
  final Color background;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final disabled = onPressed == null;
    return SizedBox(
      width: 84,
      height: 84,
      child: TextButton(
        onPressed: onPressed,
        style: TextButton.styleFrom(
          shape: const CircleBorder(),
          backgroundColor: background,
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 17,
            color: disabled ? color.withValues(alpha: 0.35) : color,
          ),
        ),
      ),
    );
  }
}

class _LapList extends StatelessWidget {
  const _LapList({
    required this.laps,
    required this.currentLap,
    required this.showCurrent,
    required this.shortest,
    required this.longest,
  });

  final List<Duration> laps;
  final Duration currentLap;
  final bool showCurrent;
  final Duration? shortest;
  final Duration? longest;

  @override
  Widget build(BuildContext context) {
    // 최신 랩이 맨 위 — 진행 중인 랩이 가장 위에 온다.
    final rows = <({int number, Duration time, Color color})>[
      if (showCurrent)
        (number: laps.length + 1, time: currentLap, color: Colors.white),
      for (var i = laps.length - 1; i >= 0; i--)
        (number: i + 1, time: laps[i], color: _colorFor(laps[i])),
    ];

    return ListView.separated(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      itemCount: rows.length,
      separatorBuilder: (_, _) => const Divider(
        height: 1,
        color: Color(0xFF2C2C2E),
      ),
      itemBuilder: (context, i) {
        final row = rows[i];
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 14),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('랩 ${row.number}',
                  style: TextStyle(fontSize: 17, color: row.color)),
              Text(
                formatLapTime(row.time),
                style: TextStyle(
                  fontSize: 17,
                  color: row.color,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Color _colorFor(Duration lap) {
    if (lap == shortest) return const Color(0xFF30D158);
    if (lap == longest) return const Color(0xFFEB4B3A);
    return Colors.white;
  }
}
