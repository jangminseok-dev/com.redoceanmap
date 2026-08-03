import 'package:flutter/material.dart';
import 'package:kakao_flutter_sdk_user/kakao_flutter_sdk_user.dart';

import 'package:app/auth.dart';
import 'package:app/home_page.dart';
import 'package:app/intro_page.dart';
import 'package:app/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await KakaoSdk.init(nativeAppKey: kakaoNativeAppKey);
  // 모바일 세션이 살아 있으면 인트로·로그인을 건너뛰고 바로 홈으로 간다.
  // 복원하는 동안은 네이티브 스플래시가 떠 있다(첫 프레임 전이라 화면이 비지 않는다).
  final signedIn = await Session.instance.restore();
  runApp(RedoceanmapApp(signedIn: signedIn));
}

class RedoceanmapApp extends StatelessWidget {
  const RedoceanmapApp({super.key, required this.signedIn});

  final bool signedIn;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'redoceanmap',
      theme: buildAppTheme(),
      home: signedIn ? const HomePage() : const IntroPage(),
    );
  }
}
