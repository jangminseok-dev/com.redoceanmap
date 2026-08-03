// 어드민 이미지 업로드 게이트웨이 — POST /admin/images.
//
// 백엔드 파이프라인의 클라이언트 쪽 끝이다:
//   이 게이트웨이 → 인바운드 라우터 → ImageUploadUseCase → ImageStoragePort → S3
// 여기서 하는 일은 멀티파트 조립과 응답 파싱뿐이다 — 형식·크기 판정, 객체 키 생성,
// 저장 위치는 전부 서버 몫이다(앱이 정하면 앱마다 규칙이 갈린다).
//
// **어드민 전용이다.** 서버가 `documents:write` 권한을 요구하므로 일반 계정은 403 "권한이 없습니다."를 받는다.
//
// 파트의 content-type은 붙이지 않는다 — 서버가 파일 앞머리(매직 넘버)로 실제 형식을 판정한다.
// 플러터 `MultipartFile`의 기본값 `application/octet-stream`을 보내도 통과하는 이유가 이것이다.

import 'dart:convert';

import 'package:http/http.dart' as http;

import 'package:app/api.dart';
import 'package:app/auth.dart';

/// 업로드 결과 — 응답 필드명은 백엔드 그대로 둔다(api.dart와 같은 규칙).
class UploadedImage {
  const UploadedImage({
    required this.key,
    required this.url,
    required this.urlExpiresIn,
    required this.bucket,
    required this.contentType,
    required this.sizeBytes,
  });

  /// S3 객체 키 — `admin/images/2026/08/<uuid>.jpg`. 다시 참조하려면 이 값을 보관한다.
  final String key;

  /// 사전서명 조회 URL. [urlExpiresIn]초 뒤 만료되므로 화면 표시용으로만 쓰고 저장하지 않는다.
  final String url;
  final int urlExpiresIn;
  final String bucket;
  final String contentType;
  final int sizeBytes;

  factory UploadedImage.fromJson(Map<String, dynamic> json) => UploadedImage(
        key: json['key'] as String,
        url: json['url'] as String,
        urlExpiresIn: json['urlExpiresIn'] as int,
        bucket: json['bucket'] as String,
        contentType: json['contentType'] as String,
        sizeBytes: json['sizeBytes'] as int,
      );
}

class AdminImageGateway {
  AdminImageGateway({http.Client? client}) : _client = client ?? http.Client();

  /// 테스트에서 갈아끼울 수 있게 주입받는다(주입하지 않으면 기본 클라이언트).
  final http.Client _client;

  /// 업로드는 조회보다 오래 걸린다 — auth.dart의 8초보다 넉넉히 잡는다.
  static const _timeout = Duration(seconds: 30);

  /// 이미지를 업로드하고 객체 키·조회 URL을 받는다.
  ///
  /// 실패는 [ApiException]으로 던진다 — 서버가 주는 한국어 `detail`을 그대로 쓴다.
  /// 400 형식·크기 거절 · 403 권한 없음 · 502 저장소 접근 실패 · 503 버킷 미설정.
  Future<UploadedImage> upload({
    required List<int> bytes,
    required String filename,
  }) async {
    // 액세스 토큰은 30분 수명이고 메모리에만 있다 — 없으면 먼저 세션을 되살린다.
    if (Session.instance.accessToken == null) await Session.instance.restore();

    var res = await _send(bytes, filename);
    if (res.statusCode == 401 && await Session.instance.restore()) {
      res = await _send(bytes, filename); // 만료된 토큰 한 번만 갱신해 재시도
    }
    if (res.statusCode != 201) throwFrom(res);

    return UploadedImage.fromJson(
      jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>,
    );
  }

  Future<http.Response> _send(List<int> bytes, String filename) async {
    final request =
        http.MultipartRequest('POST', Uri.parse('$apiBase/admin/images'))
          ..files.add(
            http.MultipartFile.fromBytes('file', bytes, filename: filename),
          );

    final token = Session.instance.accessToken;
    if (token != null) request.headers['Authorization'] = 'Bearer $token';

    final streamed = await _client.send(request).timeout(_timeout);
    return http.Response.fromStream(streamed);
  }
}
