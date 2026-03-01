import java.awt.*;
import java.awt.event.*;
import java.io.*;
import java.util.zip.*;
import javax.swing.*;

public class R extends JFrame implements KeyListener {
    private final StringBuilder hex = new StringBuilder();
    private final JLabel countLabel;
    private long startTime = 0;
    private boolean capturing = false;
    private int charCount = 0;
    private int lastDisplayCount = 0;
    private final Timer displayTimer;

    public R() {
        super("TextBridge");
        setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);
        addWindowListener(new WindowAdapter() {
            @Override public void windowClosing(WindowEvent e) { finish(); System.exit(0); }
        });
        setSize(100, 50);
        setLocationRelativeTo(null);
        setAlwaysOnTop(true);
        JPanel panel = new JPanel(new BorderLayout());
        panel.setBorder(BorderFactory.createEmptyBorder(2, 5, 2, 5));
        panel.setBackground(new Color(30, 30, 30));

        countLabel = new JLabel("0");
        countLabel.setForeground(Color.WHITE);
        countLabel.setFont(new Font("Consolas", Font.PLAIN, 10));
        countLabel.setHorizontalAlignment(SwingConstants.CENTER);

        panel.add(countLabel, BorderLayout.CENTER);
        add(panel);
        addKeyListener(this);
        setFocusable(true);
        requestFocusInWindow();

        displayTimer = new Timer(100, e -> {
            if (charCount != lastDisplayCount && capturing) {
                countLabel.setText(String.valueOf(charCount));
                lastDisplayCount = charCount;
            }
        });
        displayTimer.start();
    }

    @Override
    public void keyPressed(KeyEvent e) {
        e.consume();
        if (e.getKeyCode() == KeyEvent.VK_ESCAPE || e.getKeyCode() == KeyEvent.VK_ENTER) {
            finish();
            return;
        }
        char ch = Character.toLowerCase(e.getKeyChar());
        if ((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f')) {
            if (!capturing) {
                capturing = true;
                startTime = System.nanoTime();
                countLabel.setForeground(new Color(255, 100, 100));
            }
            hex.append(ch);
            charCount++;
        }
    }

    @Override public void keyReleased(KeyEvent e) { e.consume(); }
    @Override public void keyTyped(KeyEvent e) { e.consume(); }

    private void finish() {
        displayTimer.stop();
        if (hex.length() == 0) {
            countLabel.setText("0");
            return;
        }

        try {
            try (FileOutputStream f = new FileOutputStream("received.hex")) {
                f.write(hex.toString().getBytes("UTF-8"));
            }
        } catch (IOException ex) {
            countLabel.setText("ERR");
            return;
        }

        int decodedLen = 0;
        try {
            String hexStr = hex.toString();
            byte[] compressed = new byte[hexStr.length() / 2];
            for (int i = 0; i < compressed.length; i++)
                compressed[i] = (byte) Integer.parseInt(hexStr.substring(i * 2, i * 2 + 2), 16);
            Inflater inf = new Inflater();
            inf.setInput(compressed);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            while (!inf.finished()) out.write(buf, 0, inf.inflate(buf));
            inf.end();
            byte[] decoded = out.toByteArray();
            try (FileOutputStream f = new FileOutputStream("output.txt")) { f.write(decoded); }
            decodedLen = new String(decoded, "UTF-8").length();
        } catch (Exception ex) {
            countLabel.setText("ERR");
            return;
        }

        countLabel.setForeground(new Color(100, 200, 100));
        countLabel.setText(String.valueOf(charCount));
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> new R().setVisible(true));
    }
}
