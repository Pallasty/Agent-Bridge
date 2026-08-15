package dev.agentbridge.companion;

final class Hex {
    private Hex() {}

    static boolean isLower(String value, int length) {
        if (value == null || value.length() != length) return false;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
        }
        return true;
    }

    static byte[] decode(String value) {
        byte[] out = new byte[value.length() / 2];
        for (int i = 0; i < value.length(); i += 2) {
            out[i / 2] = (byte) Integer.parseInt(value.substring(i, i + 2), 16);
        }
        return out;
    }

    static String encode(byte[] value) {
        char[] alphabet = "0123456789abcdef".toCharArray();
        char[] out = new char[value.length * 2];
        for (int i = 0; i < value.length; i++) {
            int b = value[i] & 0xff;
            out[i * 2] = alphabet[b >>> 4];
            out[i * 2 + 1] = alphabet[b & 0x0f];
        }
        return new String(out);
    }
}
