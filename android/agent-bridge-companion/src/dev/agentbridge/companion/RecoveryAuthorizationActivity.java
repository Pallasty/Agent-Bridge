package dev.agentbridge.companion;

import android.app.Activity;
import android.hardware.biometrics.BiometricPrompt;
import android.hardware.biometrics.BiometricManager;
import android.app.KeyguardManager;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;
import java.util.concurrent.Executor;

public final class RecoveryAuthorizationActivity extends Activity {
    public static final String PREFS="agent_bridge_companion";
    public static final String RECEIPT_KEY="recovery_authorization_receipt";
    public static final String PUBLIC_KEY="recovery_authorization_public_key_b64";
    private static final String BIOMETRIC_ALIAS="agent_bridge_recovery_authorization_es256_strong_v1";
    private static final String CREDENTIAL_ALIAS="agent_bridge_recovery_authorization_es256_credential_v1";
    private TextView state;
    private String operationId, recordSha, requestSha, workspaceSha, sessionSha, nonce;

    @Override protected void onCreate(Bundle saved) {
        super.onCreate(saved); getSharedPreferences(PREFS,MODE_PRIVATE).edit().remove(RECEIPT_KEY).commit();
        operationId=getIntent().getStringExtra("operation_id"); recordSha=getIntent().getStringExtra("record_sha256");
        requestSha=getIntent().getStringExtra("request_sha256"); workspaceSha=getIntent().getStringExtra("workspace_sha256");
        sessionSha=getIntent().getStringExtra("session_sha256"); nonce=getIntent().getStringExtra("request_nonce");
        LinearLayout panel=new LinearLayout(this); panel.setOrientation(LinearLayout.VERTICAL); panel.setPadding(32,32,32,32);
        TextView title=new TextView(this); title.setText("Authorize recovery review?"); title.setTextSize(24); panel.addView(title);
        TextView detail=new TextView(this); detail.setText("Action: next\nOperation: "+shortId(operationId)
                +"\nRecord: "+shortId(recordSha)+"\nWorkspace: "+shortId(workspaceSha)
                +"\n\nThis signs one exact, short-lived review receipt. It does not execute recovery."); detail.setTextSize(17); panel.addView(detail);
        state=new TextView(this); state.setText("Not authorized"); panel.addView(state);
        Button approve=new Button(this); approve.setText("Confirm with device authentication"); panel.addView(approve);
        Button cancel=new Button(this); cancel.setText("Cancel"); panel.addView(cancel);
        approve.setOnClickListener(new View.OnClickListener(){ public void onClick(View v){ beginAuthentication(); }});
        cancel.setOnClickListener(new View.OnClickListener(){ public void onClick(View v){ finish(); }}); setContentView(panel);
    }

    private void beginAuthentication() {
        if (android.os.Build.VERSION.SDK_INT < 33) { state.setText("Unavailable: Android 13 or newer required"); return; }
        try {
            BiometricManager manager=getSystemService(BiometricManager.class);
            if (manager == null || manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                    != BiometricManager.BIOMETRIC_SUCCESS) { beginCredentialAuthentication(); return; }
        } catch (RuntimeException error) {
            state.setText("Unavailable [biometric-check]: biometric capability check failed"); return;
        }
        final KeyPair pair;
        try { pair=loadOrCreateKey(BIOMETRIC_ALIAS, 0, KeyProperties.AUTH_BIOMETRIC_STRONG); }
        catch (Exception error) { state.setText("Unavailable [key-create]: secure signing key is not available"); return; }
        final Signature signature;
        try {
            signature=Signature.getInstance("SHA256withECDSA");
            signature.initSign(pair.getPrivate());
        } catch (Exception error) { state.setText("Unavailable [key-init]: secure signing key is not usable"); return; }
        try {
            BiometricPrompt prompt=new BiometricPrompt.Builder(this).setTitle("Confirm recovery authorization")
                    .setSubtitle("Sign one exact receipt; no recovery action will run")
                    .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                    .setNegativeButton("Cancel", getMainExecutor(), (dialog, which) ->
                            state.setText("Not authorized: cancelled")).build();
            Executor executor=new Executor(){ public void execute(Runnable command){ runOnUiThread(command); }};
            prompt.authenticate(new BiometricPrompt.CryptoObject(signature), new CancellationSignal(), executor,
                new BiometricPrompt.AuthenticationCallback(){
                    @Override public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result){ sign(result.getCryptoObject().getSignature(),pair); }
                    @Override public void onAuthenticationError(int code, CharSequence message){ state.setText("Not authorized: "+message); }
                });
        } catch (Exception error) { state.setText("Unavailable [prompt]: biometric prompt could not start"); }
    }

    private void beginCredentialAuthentication() {
        KeyguardManager keyguard=getSystemService(KeyguardManager.class);
        if (keyguard == null || !keyguard.isDeviceSecure()) {
            state.setText("Unavailable [device-credential]: configure a screen lock"); return;
        }
        try {
            BiometricPrompt prompt=new BiometricPrompt.Builder(this).setTitle("Confirm recovery authorization")
                    .setSubtitle("Use the device PIN, pattern, or password to sign one exact receipt")
                    .setAllowedAuthenticators(BiometricManager.Authenticators.DEVICE_CREDENTIAL).build();
            Executor executor=new Executor(){ public void execute(Runnable command){ runOnUiThread(command); }};
            prompt.authenticate(new CancellationSignal(), executor, new BiometricPrompt.AuthenticationCallback(){
                @Override public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                    try {
                        KeyPair pair=loadOrCreateKey(CREDENTIAL_ALIAS,15,KeyProperties.AUTH_DEVICE_CREDENTIAL);
                        Signature signature=Signature.getInstance("SHA256withECDSA"); signature.initSign(pair.getPrivate());
                        sign(signature,pair);
                    } catch (Exception error) { state.setText("Not authorized [credential-sign]: signing key unavailable"); }
                }
                @Override public void onAuthenticationError(int code, CharSequence message){ state.setText("Not authorized: "+message); }
            });
        } catch (RuntimeException error) { state.setText("Unavailable [credential-prompt]: device credential prompt could not start"); }
    }

    private KeyPair loadOrCreateKey(String alias, int validitySeconds, int authenticationType) throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (!store.containsAlias(alias)) {
            KeyPairGenerator generator=KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC,"AndroidKeyStore");
            generator.initialize(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_SIGN)
                    .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .setUserAuthenticationRequired(true).setUserAuthenticationParameters(validitySeconds,
                        authenticationType).setInvalidatedByBiometricEnrollment(true).build());
            generator.generateKeyPair();
        }
        return new KeyPair(store.getCertificate(alias).getPublicKey(), (java.security.PrivateKey)store.getKey(alias,null));
    }

    private void sign(Signature signature, KeyPair pair) {
        try {
            long issued=System.currentTimeMillis()/1000L;
            String canonical=RecoveryAuthorizationProtocol.canonicalReceipt(operationId,recordSha,requestSha,workspaceSha,
                    sessionSha,issued,issued+120,"android-keystore:companion-v0",nonce);
            signature.update(canonical.getBytes("UTF-8")); String receipt=RecoveryAuthorizationProtocol.receiptToken(canonical,signature.sign());
            String publicKey=RecoveryAuthorizationProtocol.publicKeyBase64(pair.getPublic().getEncoded());
            getSharedPreferences(PREFS,MODE_PRIVATE).edit().putString(RECEIPT_KEY,receipt).putString(PUBLIC_KEY,publicKey).commit();
            state.setText("Authorized once. Receipt expires in 2 minutes; no action was executed.");
        } catch (Exception error) { state.setText("Not authorized: signing failed"); }
    }
    private static String shortId(String value){ return value==null?"invalid":(value.length()<=16?value:value.substring(0,8)+"…"+value.substring(value.length()-8)); }
}
