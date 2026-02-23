# Compressed 모드 설계

## 개요

기존 Direct 모드(한글→두벌식 키코드 HID 주입) 유지 + Compressed 모드(zlib+hex) 추가.
펌웨어/프로토콜 변경 없음. Flutter 앱에서만 처리.

## 배경

- Direct 모드: 짧은 텍스트 즉시 입력. 한글→로마자 키코드 변환 + 한영전환 토글.
- Compressed 모드: 긴 문서 전송. 텍스트→zlib 압축→hex 인코딩→ASCII 타이핑→PC에서 디코딩.
- 1만자 한글 기준 97% 시간 단축 (97초→3초).

## 데이터 흐름

### Compressed 모드

```
사용자 입력 텍스트
  → utf8.encode() → Uint8List (UTF-8 bytes)
  → ZLibCodec().encode() → Uint8List (zlib compressed, Adler-32 내장)
  → hex encode (byte → 2-char lowercase hex) → String "789c..."
  → 기존 textToKeycodes() → List<KeycodePair> (한영전환 없음, Shift 없음)
  → 기존 chunkKeycodes() → List<KeycodeChunk>
  → 기존 BLE 프로토콜 전송
  → PC 메모장에 hex 문자열 타이핑
  → 사용자가 data.txt 저장 → java H data.txt → output.txt
```

### 디코더 전송

```
앱 내장 H.java 코드 (~350자)
  → 텍스트 영역에 삽입 → 사용자가 수동 전송
```

## 변경 파일

### 신규: `lib/services/compression_service.dart`

```dart
class CompressionService {
  static const String decoderJava = '...'; // H.java (~350자)
  static String compressToHex(String text);
  static ({int originalBytes, int compressedBytes, int hexChars})
      compressionInfo(String text);
}
```

### 변경: `lib/services/settings_service.dart`

- `TransmissionMode` enum: `direct`, `compressed`
- Compressed 전용 딜레이: `compressedPressDelay` (1ms), `compressedReleaseDelay` (1ms), `compressedWarmupDelay` (50ms)
- SharedPreferences 저장/로드

### 변경: `lib/services/transmission_service.dart`

- `sendText()` 모드 분기:
  - Direct: 기존 흐름 (textToKeycodes → chunk → BLE)
  - Compressed: compressToHex → textToKeycodes → chunk → BLE
- Compressed 모드일 때 compressed 딜레이 값으로 SET_DELAY 전송

### 변경: `lib/screens/home_screen.dart`

- 모드 토글: 전송 버튼 왼쪽에 작은 `[D | C]` SegmentedButton
- 디코더 버튼: AppBar 붙여넣기 아이콘 옆에 배치. 탭 시 텍스트 영역에 H.java 삽입
- 문자 수 표시 모드별 분기:
  - Direct: `152자 → 380 키코드`
  - Compressed: `152자 → 48 bytes → 96 hex → 96 키코드 (압축률 68%)`

### 변경: `lib/screens/settings_screen.dart`

- Compressed 전용 딜레이 슬라이더 3개 (키 누름, 키 해제, 워밍업)

### 변경 없음

- `keycode_service.dart` — hex 문자는 기존 ASCII 매핑으로 처리
- `protocol.dart` — 프로토콜 커맨드 변경 없음
- `ble_service.dart` — BLE 통신 계층 변경 없음
- `textbridge.c` — 펌웨어 변경 없음

## 설계 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 펌웨어 변경 | 없음 | hex는 ASCII, 기존 KEYCODE 커맨드로 전송 |
| 한영전환 | Compressed는 PC 영문 모드 가정 | hex는 0-9, a-f만 사용 |
| 인코딩 | UTF-8 고정 | 노션 요구사항 확정 |
| 에러 검증 | zlib Adler-32 내장 | 추가 구현 없음 |
| 에러 시 | PC에서 DataFormatException | 앱에서 수동 재전송 |
| 디코더 | H.java 앱 내장 | 텍스트 영역에 삽입, 사용자가 수동 전송 |

## 테스트

### Dart 단위 테스트 (`compression_service_test.dart`)

- compressToHex 왕복: text → hex → unhex → inflate → text 일치
- compressionInfo 정확성
- 엣지 케이스: 빈 문자열, 영문, 한글, 혼합, 이모지

### 설정 테스트 (`settings_service_test.dart`)

- TransmissionMode + compressed 딜레이 저장/로드

### 브릿지 테스트 (`test_app_bridge.py`)

- Dart compressToHex vs Python zlib+hex 출력 일치 확인

## H.java 디코더 코드

```java
import java.util.zip.*;
import java.io.*;
import java.nio.file.*;
class H{public static void main(String[] a)throws Exception{
String s=new String(Files.readAllBytes(Paths.get(a[0]))).trim();
byte[]b=new byte[s.length()/2];
for(int i=0;i<b.length;i++)b[i]=(byte)Integer.parseInt(s.substring(i*2,i*2+2),16);
Inflater i=new Inflater();i.setInput(b);
ByteArrayOutputStream o=new ByteArrayOutputStream();
byte[]buf=new byte[4096];
while(!i.finished()){int n=i.inflate(buf);o.write(buf,0,n);}
i.end();
Files.write(Paths.get("output.txt"),o.toByteArray());
System.out.println("ok "+o.size()+"b");}}
```
