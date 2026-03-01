import 'dart:convert';
import 'dart:io';

class CompressionService {
  /// R.java receiver + decoder. User sends this to PC once via Direct mode.
  /// Usage: javac R.java (once) → java R (each time, GUI window opens)
  static const String decoderJava =
      'import java.awt.*;\n'
      'import java.awt.event.*;\n'
      'import java.io.*;\n'
      'import java.util.zip.*;\n'
      'import javax.swing.*;\n'
      'public class R extends JFrame implements KeyListener{\n'
      'private final StringBuilder hex=new StringBuilder();\n'
      'private final JLabel countLabel;\n'
      'private long startTime=0;\n'
      'private boolean capturing=false;\n'
      'private int charCount=0;\n'
      'private int lastDisplayCount=0;\n'
      'private final Timer displayTimer;\n'
      'public R(){\n'
      'super("TextBridge");\n'
      'setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);\n'
      'addWindowListener(new WindowAdapter(){\n'
      '@Override public void windowClosing(WindowEvent e){finish();System.exit(0);}});\n'
      'setSize(100,50);\n'
      'setLocationRelativeTo(null);\n'
      'setAlwaysOnTop(true);\n'
      'JPanel panel=new JPanel(new BorderLayout());\n'
      'panel.setBorder(BorderFactory.createEmptyBorder(2,5,2,5));\n'
      'panel.setBackground(new Color(30,30,30));\n'
      'countLabel=new JLabel("0");\n'
      'countLabel.setForeground(Color.WHITE);\n'
      'countLabel.setFont(new Font("Consolas",Font.PLAIN,10));\n'
      'countLabel.setHorizontalAlignment(SwingConstants.CENTER);\n'
      'panel.add(countLabel,BorderLayout.CENTER);\n'
      'add(panel);\n'
      'addKeyListener(this);\n'
      'setFocusable(true);\n'
      'requestFocusInWindow();\n'
      'displayTimer=new Timer(100,e->{\n'
      'if(charCount!=lastDisplayCount&&capturing){\n'
      'countLabel.setText(String.valueOf(charCount));\n'
      'lastDisplayCount=charCount;}});\n'
      'displayTimer.start();}\n'
      '@Override public void keyPressed(KeyEvent e){\n'
      'e.consume();\n'
      'if(e.getKeyCode()==KeyEvent.VK_ESCAPE||e.getKeyCode()==KeyEvent.VK_ENTER){\n'
      'finish();return;}\n'
      'char ch=Character.toLowerCase(e.getKeyChar());\n'
      'if((ch>=\'0\'&&ch<=\'9\')||(ch>=\'a\'&&ch<=\'f\')){\n'
      'if(!capturing){\n'
      'capturing=true;\n'
      'startTime=System.nanoTime();\n'
      'countLabel.setForeground(new Color(255,100,100));}\n'
      'hex.append(ch);\n'
      'charCount++;}}\n'
      '@Override public void keyReleased(KeyEvent e){e.consume();}\n'
      '@Override public void keyTyped(KeyEvent e){e.consume();}\n'
      'private void finish(){\n'
      'displayTimer.stop();\n'
      'if(hex.length()==0){countLabel.setText("0");return;}\n'
      'try{try(FileOutputStream f=new FileOutputStream("received.hex")){\n'
      'f.write(hex.toString().getBytes("UTF-8"));}}\n'
      'catch(IOException ex){countLabel.setText("ERR");return;}\n'
      'try{\n'
      'String hexStr=hex.toString();\n'
      'byte[]compressed=new byte[hexStr.length()/2];\n'
      'for(int i=0;i<compressed.length;i++)\n'
      'compressed[i]=(byte)Integer.parseInt(hexStr.substring(i*2,i*2+2),16);\n'
      'Inflater inf=new Inflater();\n'
      'inf.setInput(compressed);\n'
      'ByteArrayOutputStream out=new ByteArrayOutputStream();\n'
      'byte[]buf=new byte[4096];\n'
      'while(!inf.finished())out.write(buf,0,inf.inflate(buf));\n'
      'inf.end();\n'
      'byte[]decoded=out.toByteArray();\n'
      'try(FileOutputStream f=new FileOutputStream("output.txt")){f.write(decoded);}}\n'
      'catch(Exception ex){countLabel.setText("ERR");return;}\n'
      'countLabel.setForeground(new Color(100,200,100));\n'
      'countLabel.setText(String.valueOf(charCount));}\n'
      'public static void main(String[]args){\n'
      'SwingUtilities.invokeLater(()->new R().setVisible(true));}}';

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
