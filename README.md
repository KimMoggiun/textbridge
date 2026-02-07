# TextBridge

폐쇄망 회사 PC에 휴대폰에서 텍스트를 전송하는 시스템.
Keychron B6 Pro 키보드(ZMK/nRF52840)를 BLE-to-USB HID 브릿지로 활용.

## 아키텍처

```
┌─────────────┐     BLE      ┌─────────────┐     USB
│  Flutter 앱  │ ──────────→ │   B6 Pro    │ ──────────→  회사 PC
│  (휴대폰)   │  TextBridge  │  (nRF52840) │    (유선)
└─────────────┘   GATT 서비스  └─────────────┘
```

- **PC 연결:** USB 유선 (1000Hz HID)
- **폰 연결:** BLE 커스텀 GATT 서비스
- **목표 속도:** 500+ chars/sec

## 구성 요소

| 구성 요소 | 설명 | 상태 |
|---|---|---|
| ZMK 펌웨어 모듈 | BLE GATT 서비스 + HID 키 입력 주입 | 설계 중 |
| Flutter 앱 | 텍스트→키코드 변환, BLE 전송, 한글 지원 | 설계 중 |

## 설계 문서

- [TextBridge 설계 문서](docs/plans/2026-02-06-textbridge-design.md)

## 관련 프로젝트

- [zmk-b6pro-backup](https://github.com/KimMoggiun/zmk-b6pro-backup) — Keychron B6 Pro ZMK 설정 백업
