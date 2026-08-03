// 백엔드 호출. 운영 도메인에 직접 붙는다.
// (www의 `/api/backend` rewrite는 Next.js 기능이라 Flutter에는 없다.)
// 응답 필드명은 백엔드 그대로 둔다 — www와 같은 규칙.

import 'dart:convert';

import 'package:http/http.dart' as http;

const apiBase = 'https://api.redoceanmap.com';

class ApiException implements Exception {
  const ApiException(this.status, this.message);

  final int status;
  final String message;

  bool get needsLogin => status == 401;

  @override
  String toString() => message;
}

/// 응답 본문의 `detail`을 그대로 쓴다 — 백엔드가 한국어 메시지를 준다.
Never throwFrom(http.Response res) {
  String message;
  try {
    final body = jsonDecode(utf8.decode(res.bodyBytes));
    message = (body is Map && body['detail'] is String)
        ? body['detail'] as String
        : 'HTTP ${res.statusCode}';
  } catch (_) {
    message = 'HTTP ${res.statusCode}';
  }
  throw ApiException(res.statusCode, message);
}

// ── GET /market/areas/showcase ──

class Showcase {
  const Showcase({
    required this.yearQuarter,
    required this.quarterFrom,
    required this.areaCount,
    required this.rows,
  });

  final int yearQuarter;
  final int quarterFrom;
  final int areaCount;
  final List<ShowcaseRow> rows;

  factory Showcase.fromJson(Map<String, dynamic> json) => Showcase(
        yearQuarter: json['yearQuarter'] as int,
        quarterFrom: json['quarterFrom'] as int,
        areaCount: json['areaCount'] as int,
        rows: (json['rows'] as List)
            .map((e) => ShowcaseRow.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class ShowcaseRow {
  const ShowcaseRow({
    required this.trdarName,
    required this.districtName,
    required this.divisionName,
    required this.salesPerStore,
    required this.storeCount,
  });

  final String trdarName;
  final String districtName;
  final String divisionName;
  final int salesPerStore;
  final int storeCount;

  factory ShowcaseRow.fromJson(Map<String, dynamic> json) => ShowcaseRow(
        trdarName: json['trdarName'] as String,
        districtName: json['districtName'] as String,
        divisionName: json['divisionName'] as String,
        salesPerStore: json['salesPerStore'] as int,
        storeCount: json['storeCount'] as int,
      );
}

Future<Showcase> fetchShowcase() async {
  final res = await http.get(Uri.parse('$apiBase/market/areas/showcase'));
  if (res.statusCode != 200) throwFrom(res);
  return Showcase.fromJson(
    jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>,
  );
}

// ── POST /chat/ask ──
// 인증이 필요한 엔드포인트다. 로그인을 붙이기 전까지는 401을 그대로 받는다.

class ChatAnswer {
  const ChatAnswer({required this.sessionId, required this.answer});

  final int sessionId;
  final String answer;

  factory ChatAnswer.fromJson(Map<String, dynamic> json) => ChatAnswer(
        sessionId: json['sessionId'] as int,
        answer: json['answer'] as String,
      );
}

Future<ChatAnswer> askChat(String prompt, {int? conversationId}) async {
  final res = await http.post(
    Uri.parse('$apiBase/chat/ask'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'prompt': prompt, 'conversationId': conversationId}),
  );
  if (res.statusCode != 200) throwFrom(res);
  return ChatAnswer.fromJson(
    jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>,
  );
}
