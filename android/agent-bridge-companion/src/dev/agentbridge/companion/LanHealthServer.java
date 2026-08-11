package dev.agentbridge.companion;

import java.io.ByteArrayOutputStream;
import java.io.Closeable;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketException;
import java.nio.charset.Charset;

public final class LanHealthServer implements Closeable {
    private static final Charset UTF_8 = Charset.forName("UTF-8");
    private static final int MAX_REQUEST_BYTES = 1024;
    private static final int MAX_RESPONSE_BYTES = 2048;
    private static final int SOCKET_TIMEOUT_MS = 2000;
    private final ServerSocket serverSocket;
    private final LanHealthProtocol protocol;
    private final HealthSupplier healthSupplier;
    private Thread thread;
    private volatile boolean closed;

    public LanHealthServer(InetAddress bindAddress, int port, String token, HealthSupplier supplier)
            throws IOException {
        if (bindAddress == null || bindAddress.isAnyLocalAddress()) {
            throw new IllegalArgumentException("LAN health requires a specific bind address");
        }
        if (supplier == null) throw new IllegalArgumentException("health supplier is required");
        protocol = new LanHealthProtocol(token);
        healthSupplier = supplier;
        serverSocket = new ServerSocket(port, 4, bindAddress);
    }

    public synchronized void start() {
        if (thread != null) return;
        thread = new Thread(new Runnable() { public void run() { acceptLoop(); } }, "AgentBridgeLanHealth");
        thread.setDaemon(true);
        thread.start();
    }

    public int getPort() { return serverSocket.getLocalPort(); }

    private void acceptLoop() {
        while (!closed) {
            try { handle(serverSocket.accept()); }
            catch (SocketException error) { if (!closed) closeQuietly(); }
            catch (IOException error) { if (!closed) closeQuietly(); }
        }
    }

    private void handle(Socket socket) {
        try {
            socket.setSoTimeout(SOCKET_TIMEOUT_MS);
            String request = readRequest(socket.getInputStream());
            LanHealthProtocol.Result result = protocol.verify(request, System.currentTimeMillis() / 1000L);
            String response;
            if (result == LanHealthProtocol.Result.OK) {
                response = "OK " + healthSupplier.healthJson();
                if (response.getBytes(UTF_8).length > MAX_RESPONSE_BYTES) response = "ERROR RESPONSE_TOO_LARGE";
            } else response = "ERROR " + result.name();
            OutputStream output = socket.getOutputStream();
            output.write(response.getBytes(UTF_8));
            output.write('\n');
            output.flush();
        } catch (IOException ignored) {
        } finally {
            try { socket.close(); } catch (IOException ignored) {}
        }
    }

    private static String readRequest(InputStream input) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        int value;
        while (output.size() <= MAX_REQUEST_BYTES && (value = input.read()) != -1 && value != '\n') {
            if (value != '\r') output.write(value);
        }
        if (output.size() > MAX_REQUEST_BYTES) return null;
        return new String(output.toByteArray(), UTF_8);
    }

    public void close() {
        closed = true;
        closeQuietly();
        Thread current;
        synchronized (this) { current = thread; }
        if (current != null && current != Thread.currentThread()) {
            try { current.join(2000L); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); }
        }
    }

    private void closeQuietly() { try { serverSocket.close(); } catch (IOException ignored) {} }

    public interface HealthSupplier { String healthJson(); }
}
