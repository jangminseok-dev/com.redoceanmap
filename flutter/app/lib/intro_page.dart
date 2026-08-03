// 앱 실행 시 첫 화면 — 인트로 영상을 한 번 재생하고 홈으로 넘어간다.

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import 'package:app/home_page.dart';
import 'package:app/theme.dart';

class IntroPage extends StatefulWidget {
  const IntroPage({super.key});

  @override
  State<IntroPage> createState() => _IntroPageState();
}

class _IntroPageState extends State<IntroPage> {
  late final VideoPlayerController _controller;
  bool _ready = false;
  bool _left = false;

  @override
  void initState() {
    super.initState();
    // 캐스케이드로 이어 붙이면 setVolume이 _controller 할당 전에 _onTick을 깨운다.
    _controller = VideoPlayerController.asset('assets/intro.mp4');
    _controller
      ..addListener(_onTick)
      ..setVolume(0);
    _start();
  }

  Future<void> _start() async {
    try {
      await _controller.initialize();
      if (!mounted) return;
      setState(() => _ready = true);
      await _controller.play();
    } catch (_) {
      // 영상이 깨져도 앱이 멈추면 안 된다 — 바로 홈으로 보낸다.
      _goHome();
    }
  }

  void _onTick() {
    final v = _controller.value;
    if (v.isInitialized && v.position >= v.duration) _goHome();
  }

  void _goHome() {
    if (_left || !mounted) return;
    _left = true;
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        transitionDuration: const Duration(milliseconds: 450),
        pageBuilder: (_, _, _) => const HomePage(),
        transitionsBuilder: (_, animation, _, child) =>
            FadeTransition(opacity: animation, child: child),
      ),
    );
  }

  @override
  void dispose() {
    _controller.removeListener(_onTick);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.foreground,
      body: Stack(
        fit: StackFit.expand,
        children: [
          if (_ready)
            FittedBox(
              fit: BoxFit.cover,
              child: SizedBox(
                width: _controller.value.size.width,
                height: _controller.value.size.height,
                child: VideoPlayer(_controller),
              ),
            ),
          // 영상 위 글씨가 묻히지 않게 아래쪽을 어둡게 깐다.
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.center,
                end: Alignment.bottomCenter,
                colors: [Colors.transparent, Color(0xCC1A1A1A)],
              ),
            ),
          ),
          const Positioned(
            left: 24,
            right: 24,
            bottom: 72,
            child: _IntroCaption(),
          ),
          Positioned(
            top: 12,
            right: 12,
            child: SafeArea(
              child: TextButton(
                onPressed: _goHome,
                style: TextButton.styleFrom(foregroundColor: Colors.white70),
                child: const Text('건너뛰기'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _IntroCaption extends StatelessWidget {
  const _IntroCaption();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'redoceanmap',
          style: TextStyle(
            fontSize: 13,
            letterSpacing: 1.2,
            color: Colors.white.withValues(alpha: 0.7),
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          '상권과 주식,\n지금 상황을 빠르게 읽어드릴게요',
          style: TextStyle(
            fontSize: 26,
            height: 1.35,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.5,
            color: Colors.white,
          ),
        ),
      ],
    );
  }
}
