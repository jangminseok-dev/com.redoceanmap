// 약관 동의 화면 — 카카오 로그인 다음, 가입 완료 이전.
//
// 카카오싱크(비즈니스 앱) 미전환이라 카카오 동의 화면을 못 쓰는 동안, 필수 약관을 우리 앱에서 받는다.
// 서버는 신규 유저에게 `status="consent_required"` + `consentToken`을 200으로 내리고(실패가 아니다),
// 이 화면이 동의를 받아 `POST /auth/mobile/consent`로 가입을 마친다.
//
// 서버에 보내는 것은 `marketingAgreed`뿐이다 — 필수 3종은 **동의 없이는 요청 자체를 보내지 않는** 것으로
// 표현한다. 카카오 회원번호는 보내지 않는다(신원은 consentToken 서명 안에만 있다).
// 명세: minseok/_docs/flutter-kakao-oauth-harness.md 8.6

import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';

import 'package:app/api.dart';
import 'package:app/auth.dart';
import 'package:app/home_page.dart';
import 'package:app/theme.dart';

/// 동의 항목 — 태그는 서버·콘솔이 쓰는 이름(`age`·`terms`·`privacy`·`marketing`)과 같게 둔다.
class _Term {
  const _Term(this.tag, this.label, {this.required = true});

  final String tag;
  final String label;
  final bool required;
}

const _terms = [
  _Term('age', '만 14세 이상입니다'),
  _Term('terms', '서비스 이용약관 동의'),
  _Term('privacy', '개인정보 수집·이용 동의'),
  _Term('marketing', '마케팅 정보 수신 동의 (선택)', required: false),
];

class ConsentPage extends StatefulWidget {
  const ConsentPage({super.key, required this.consentToken});

  /// 서버가 서명한 신원 증표 — 수명 10분이다. 만료되면 로그인부터 다시 해야 한다.
  final String consentToken;

  @override
  State<ConsentPage> createState() => _ConsentPageState();
}

class _ConsentPageState extends State<ConsentPage> {
  /// 체크 상태는 태그 집합 하나로 관리한다(항목마다 bool을 두지 않는다).
  final _agreed = <String>{};
  bool _busy = false;
  String? _error;

  bool get _requiredMet =>
      _terms.where((t) => t.required).every((t) => _agreed.contains(t.tag));

  bool get _allChecked => _agreed.length == _terms.length;

  void _toggle(String tag, bool? checked) {
    setState(() {
      if (checked ?? false) {
        _agreed.add(tag);
      } else {
        _agreed.remove(tag);
      }
    });
  }

  void _toggleAll(bool? checked) {
    setState(() {
      _agreed
        ..clear()
        ..addAll((checked ?? false) ? _terms.map((t) => t.tag) : const <String>[]);
    });
  }

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final outcome = await Session.instance.completeConsent(
        consentToken: widget.consentToken,
        marketingAgreed: _agreed.contains('marketing'),
      );
      if (!mounted) return;
      if (outcome.needsConsent) {
        // 가입이 끝났으면 세션이 와야 한다 — 안 왔으면 진행하지 않는다.
        setState(() {
          _busy = false;
          _error = '가입을 마치지 못했습니다. 다시 시도해 주세요.';
        });
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const HomePage()),
      );
    } catch (error) {
      if (kDebugMode) debugPrint('약관 동의 실패: $error');
      if (!mounted) return;
      setState(() {
        _busy = false;
        // 서버가 주는 한국어 메시지는 그대로 쓴다(동의 토큰 만료 401 포함).
        _error = error is ApiException
            ? error.message
            : '가입에 실패했습니다. 잠시 후 다시 시도해 주세요.';
      });
    }
  }

  void _restart() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const AuthPage()),
    );
  }

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
              const SizedBox(height: 32),
              Text('redoceanmap', style: text.bodySmall),
              const SizedBox(height: 10),
              Text('약관에 동의하고\n가입을 마칠까요?', style: text.displaySmall),
              const SizedBox(height: 12),
              Text(
                '필수 항목에 동의해야 가입이 완료됩니다.',
                style: text.bodyMedium?.copyWith(
                  color: AppColors.foregroundMuted,
                ),
              ),
              const SizedBox(height: 24),
              // 작은 화면·가로 모드에서도 넘치지 않게 목록만 스크롤시킨다.
              Expanded(
                child: SingleChildScrollView(
                  child: Container(
                    decoration: cardDecoration,
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Column(
                      children: [
                        CheckboxListTile(
                          value: _allChecked,
                          onChanged: _busy ? null : _toggleAll,
                          controlAffinity: ListTileControlAffinity.leading,
                          title: Text('전체 동의', style: text.titleMedium),
                        ),
                        const Divider(height: 1),
                        for (final term in _terms)
                          CheckboxListTile(
                            value: _agreed.contains(term.tag),
                            onChanged: _busy
                                ? null
                                : (checked) => _toggle(term.tag, checked),
                            controlAffinity: ListTileControlAffinity.leading,
                            title: Text(term.label, style: text.bodyMedium),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              if (_error != null) ...[
                Text(
                  _error!,
                  style: text.bodySmall?.copyWith(color: AppColors.brand),
                ),
                TextButton(
                  onPressed: _busy ? null : _restart,
                  child: const Text('처음부터 다시 로그인'),
                ),
                const SizedBox(height: 4),
              ],
              SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(
                  onPressed: (_busy || !_requiredMet) ? null : _submit,
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.brand,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: AppColors.brand.withValues(
                      alpha: 0.35,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(AppRadius.icon),
                    ),
                  ),
                  child: _busy
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text(
                          '동의하고 시작하기',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }
}
