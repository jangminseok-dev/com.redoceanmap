// 카카오 로그인 화면 + 모바일 세션 보관.
//
// 카카오 SDK는 최초 신원 확인에만 쓴다 — 프로필 조회(`UserApi.instance.me()`)는 서버 몫이라
// 앱에서 호출하지 않는다. 서버로 넘기는 것은 카카오 액세스 토큰과 기기 식별자뿐이고,
// 서버가 카카오에 신원을 직접 확인한 뒤 자체 JWT를 발급한다.
// 리프레시 토큰은 서버가 Redis 모바일 DB(db 1)에 적재하고, 앱은 같은 값을 보안 저장소에 남긴다.
//
// 명세: minseok/_docs/flutter-kakao-oauth-harness.md · flutter/_docs/flutter-kakao-oauth-harness.md

import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:kakao_flutter_sdk_user/kakao_flutter_sdk_user.dart';

import 'package:app/api.dart';
import 'package:app/home_page.dart';
import 'package:app/theme.dart';

/// 토큰 발급은 개인키를 가진 auth 프로세스만 한다 — api.dart의 `apiBase`와 다른 오리진이다.
const authBase = 'https://auth.redoceanmap.com';

/// 앱 키는 소스에 넣지 않는다 — `--dart-define=KAKAO_NATIVE_APP_KEY=...`로 주입한다.
const kakaoNativeAppKey = String.fromEnvironment('KAKAO_NATIVE_APP_KEY');

const _timeout = Duration(seconds: 8);

/// 모바일 세션 — 액세스 토큰은 메모리에만, 리프레시 토큰만 보안 저장소에 남긴다.
class Session {
  Session._();

  static final Session instance = Session._();

  static const _storage = FlutterSecureStorage();
  static const _refreshKey = 'mobile_refresh_token';
  static const _deviceKey = 'mobile_device_id';

  /// 30분 수명이라 디스크에 남기지 않는다 — 앱 재시작 시 [restore]로 다시 받는다.
  String? accessToken;

  /// 저장된 리프레시 토큰으로 세션을 되살린다(앱 시작 시 1회).
  Future<bool> restore() async {
    final refreshToken = await _storage.read(key: _refreshKey);
    if (refreshToken == null) return false;
    try {
      await _authenticate('/auth/mobile/refresh', {
        'refreshToken': refreshToken,
      });
      return true;
    } on ApiException catch (error) {
      // 서버가 거절한 세션만 지운다 — 네트워크 실패면 토큰을 남겨 다음 실행에서 다시 시도한다.
      if (error.needsLogin) await _storage.delete(key: _refreshKey);
      return false;
    } catch (_) {
      return false;
    }
  }

  /// 카카오 로그인 → 서버 신원 확인 → 자체 JWT 수령.
  Future<void> signInWithKakao() async {
    if (kakaoNativeAppKey.isEmpty) {
      throw const ApiException(
        0, // HTTP 응답 이전에 막힌 설정 오류 — 상태 코드가 없다.
        '카카오 앱 키가 주입되지 않았습니다. (--dart-define=KAKAO_NATIVE_APP_KEY)',
      );
    }
    final kakaoToken = await _loginWithKakao();
    try {
      await _authenticate('/auth/mobile/kakao', {
        'accessToken': kakaoToken.accessToken,
        'deviceId': await _deviceId(),
      });
    } finally {
      // 카카오 토큰은 신원 확인용이다 — 저장하지 않는다. SDK가 보관한 것도 함께 버린다.
      try {
        await UserApi.instance.logout();
      } catch (_) {}
    }
  }

  /// 카카오톡이 있으면 앱으로, 없거나 실패하면 카카오계정(웹)으로 — 공식 가이드의 기본 흐름.
  Future<OAuthToken> _loginWithKakao() async {
    if (await isKakaoTalkInstalled()) {
      try {
        return await UserApi.instance.loginWithKakaoTalk();
      } catch (error) {
        // 사용자가 취소했으면 계정 로그인으로 끌고 가지 않는다.
        if (_isCancelled(error)) rethrow;
      }
    }
    return UserApi.instance.loginWithKakaoAccount();
  }

  Future<void> _authenticate(String path, Map<String, Object?> body) async {
    final res = await http
        .post(
          Uri.parse('$authBase$path'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body), // 카카오 토큰은 body로만 — 쿼리는 액세스 로그에 남는다
        )
        .timeout(_timeout);
    if (res.statusCode != 200) throwFrom(res);
    final json = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    accessToken = json['accessToken'] as String;
    await _storage.write(
      key: _refreshKey,
      value: json['refreshToken'] as String,
    );
  }

  /// 기기 식별자 — 앱이 만든 난수다. 광고·하드웨어 식별자를 쓰지 않는다.
  Future<String> _deviceId() async {
    final saved = await _storage.read(key: _deviceKey);
    if (saved != null) return saved;
    final random = Random.secure();
    final id = List.generate(
      16,
      (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
    ).join();
    await _storage.write(key: _deviceKey, value: id);
    return id;
  }
}

/// 취소는 오류가 아니다 — 화면에 실패 메시지를 띄우지 않기 위해 구분한다.
bool _isCancelled(Object error) =>
    (error is PlatformException && error.code == 'CANCELED') ||
    (error is KakaoClientException &&
        error.reason == ClientErrorCause.cancelled);

/// 로그인 화면 — 인트로 다음, 홈 이전. 카카오 로그인 버튼 하나뿐이다.
class AuthPage extends StatefulWidget {
  const AuthPage({super.key});

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  bool _busy = false;
  String? _error;

  Future<void> _signIn() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await Session.instance.signInWithKakao();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const HomePage()),
      );
    } catch (error) {
      // 화면에는 사유를 세분해 노출하지 않는다(명세 7절) — 디버그 빌드 콘솔에만 남긴다.
      if (kDebugMode) debugPrint('카카오 로그인 실패: $error');
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = _isCancelled(error) ? null : _messageOf(error);
      });
    }
  }

  /// 서버가 주는 한국어 메시지는 그대로 쓰고, 그 밖의 오류는 사유를 세분해 노출하지 않는다.
  String _messageOf(Object error) =>
      error is ApiException ? error.message : '로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.';

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Spacer(),
              Text('redoceanmap', style: text.bodySmall),
              const SizedBox(height: 10),
              Text('상권과 주식,\n로그인하고 이어서 볼까요?', style: text.displaySmall),
              const SizedBox(height: 12),
              Text(
                '카카오 계정으로 3초 만에 시작할 수 있어요.',
                style: text.bodyMedium?.copyWith(
                  color: AppColors.foregroundMuted,
                ),
              ),
              const Spacer(),
              if (_error != null) ...[
                Text(
                  _error!,
                  style: text.bodySmall?.copyWith(color: AppColors.brand),
                ),
                const SizedBox(height: 12),
              ],
              _KakaoButton(busy: _busy, onPressed: _busy ? null : _signIn),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }
}

class _KakaoButton extends StatelessWidget {
  const _KakaoButton({required this.busy, required this.onPressed});

  // 카카오 로그인 버튼 규정색 — 배경 #FEE500, 글자는 불투명도 85%의 검정.
  static const _kakaoYellow = Color(0xFFFEE500);
  static const _kakaoLabel = Color(0xD9000000);

  final bool busy;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: FilledButton(
        onPressed: onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: _kakaoYellow,
          foregroundColor: _kakaoLabel,
          disabledBackgroundColor: _kakaoYellow.withValues(alpha: 0.6),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.icon),
          ),
        ),
        child: busy
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: _kakaoLabel,
                ),
              )
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.chat_bubble, size: 18),
                  SizedBox(width: 8),
                  Text(
                    '카카오로 로그인',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
      ),
    );
  }
}
