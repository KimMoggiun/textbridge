import 'dart:convert';
import 'dart:io';

class CompressionService {
  /// H.java hex decoder. User sends this to PC once via Direct mode.
  /// Usage: javac H.java (once) → java H data.txt (each time)
  static const String decoderJava =
      'import java.util.zip.*;\n'
      'import java.io.*;\n'
      'import java.nio.file.*;\n'
      'class H{public static void main(String[] a)throws Exception{\n'
      'String s=new String(Files.readAllBytes(Paths.get(a[0]))).replaceAll("[^0-9a-fA-F]","");\n'
      'byte[]b=new byte[s.length()/2];\n'
      'for(int i=0;i<b.length;i++)b[i]=(byte)Integer.parseInt(s.substring(i*2,i*2+2),16);\n'
      'Inflater i=new Inflater();i.setInput(b);\n'
      'ByteArrayOutputStream o=new ByteArrayOutputStream();\n'
      'byte[]buf=new byte[4096];\n'
      'while(!i.finished()){int n=i.inflate(buf);o.write(buf,0,n);}\n'
      'i.end();\n'
      'Files.write(Paths.get("output.txt"),o.toByteArray());\n'
      'System.out.println("ok "+o.size()+"b");}}';

  /// Compress text to hex string: UTF-8 → zlib → lowercase hex.
  static String compressToHex(String text) {
    final utf8Bytes = utf8.encode(text);
    final compressed = ZLibCodec().encode(utf8Bytes);
    final sb = StringBuffer();
    for (final b in compressed) {
      sb.write(b.toRadixString(16).padLeft(2, '0'));
    }
    return sb.toString();
  }

  /// Get compression size info for UI display.
  static ({int originalBytes, int compressedBytes, int hexChars})
      compressionInfo(String text) {
    final utf8Bytes = utf8.encode(text);
    final compressed = ZLibCodec().encode(utf8Bytes);
    return (
      originalBytes: utf8Bytes.length,
      compressedBytes: compressed.length,
      hexChars: compressed.length * 2,
    );
  }
}
