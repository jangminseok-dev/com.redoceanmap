import type { Metadata } from "next";

import AppFooter from "@/components/shell/AppFooter";

export const metadata: Metadata = {
  title: "개인정보처리방침 — redoceanmap",
};

const SECTIONS: { title: string; body: string[] }[] = [
  {
    title: "1. 수집하는 개인정보 항목 및 수집 방법",
    body: [
      "이메일 가입 시: 이메일 주소, 이름, 비밀번호(복호화 불가능한 해시로만 저장).",
      "소셜 로그인(구글·카카오·네이버) 시: 해당 제공자로부터 이메일 주소, 이름을 제공받습니다. 비밀번호는 수집하지 않습니다.",
      "서비스 이용 과정에서 로그인 유지를 위한 토큰이 발급·저장됩니다.",
    ],
  },
  {
    title: "2. 개인정보의 수집 및 이용 목적",
    body: [
      "회원 식별 및 로그인 등 회원제 서비스 제공.",
      "AI 채팅 등 개인화 기능 제공 및 서비스 운영을 위한 공지.",
      "(선택 동의 시) 서비스 소식 등 마케팅 정보 전달.",
    ],
  },
  {
    title: "3. 개인정보의 보유 및 이용 기간",
    body: [
      "회원 탈퇴 시까지 보유하며, 탈퇴 요청 시 지체 없이 파기합니다.",
      "로그인 유지용 리프레시 토큰은 발급 후 14일이 지나면 자동 소멸합니다.",
      "관계 법령에 따라 보존이 필요한 경우 해당 법령이 정한 기간 동안 보관합니다.",
    ],
  },
  {
    title: "4. 개인정보의 제3자 제공 및 처리 위탁",
    body: [
      "수집한 개인정보를 제3자에게 제공하거나 외부에 처리를 위탁하지 않습니다.",
      "모든 회원 정보는 서비스 제공자가 직접 운영하는 서버에 저장됩니다.",
      "법령에 근거한 수사기관 등의 적법한 요청이 있는 경우는 예외로 합니다.",
    ],
  },
  {
    title: "5. 정보주체의 권리",
    body: [
      "회원은 언제든지 자신의 개인정보에 대한 열람·정정·삭제·처리 정지를 요청할 수 있습니다. 요청은 이메일(jang971121@gmail.com)로 접수하며, 지체 없이 처리합니다.",
    ],
  },
  {
    title: "6. 개인정보의 파기 절차 및 방법",
    body: [
      "보유 기간이 경과하거나 처리 목적이 달성된 개인정보는 재생할 수 없는 방법으로 지체 없이 파기합니다. 전자적 파일 형태의 정보는 복구 불가능한 방식으로 삭제합니다.",
    ],
  },
  {
    title: "7. 개인정보의 안전성 확보 조치",
    body: [
      "비밀번호는 bcrypt 해시로 저장되어 서비스 제공자도 원문을 알 수 없습니다.",
      "소셜 로그인 계정에는 비밀번호 로그인 경로가 열리지 않도록 무작위 값이 저장됩니다.",
      "인증 토큰은 유효 기간을 짧게 유지하고, 리프레시 토큰은 1회 사용 시 폐기·재발급(회전)됩니다.",
    ],
  },
  {
    title: "8. 개인정보 보호책임자",
    body: [
      "성명: 장민석",
      "연락처: jang971121@gmail.com",
      "개인정보 관련 문의·불만 처리·피해 구제를 위 연락처로 요청할 수 있습니다.",
    ],
  },
  {
    title: "9. 고지의 의무",
    body: [
      "이 방침의 내용이 추가·삭제·수정될 경우 시행 7일 전부터 서비스 내 공지사항을 통해 알립니다.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12">
      <h1 className="text-2xl font-bold">redoceanmap 개인정보처리방침</h1>
      <p className="mt-2 text-sm text-foreground-muted">시행일: 2026년 7월 20일</p>
      {SECTIONS.map((s) => (
        <section key={s.title} className="mt-8">
          <h2 className="font-semibold">{s.title}</h2>
          {s.body.map((p, i) => (
            <p key={i} className="mt-2 text-sm leading-relaxed text-foreground-muted">
              {p}
            </p>
          ))}
        </section>
      ))}
      <AppFooter />
    </main>
  );
}
