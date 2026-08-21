package dev.agentbridge.companion;

import android.app.Activity;
import android.hardware.biometrics.BiometricPrompt;
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
import java.util.concurrent.Executor;

public final class RecoveryAuthorizationActivity extends Activity {
    public static final String PREFS="agent_bridge_companion";
    public static final String RECEIPT_KEY="recovery_authorization_receipt";
    public static final String PUBLIC_KEY="recovery_authorization_public_key_b64";
    private static final String ALIAS="agent_bridge_recovery_authorization_ed25519_v0";
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
            final KeyPair pair=loadOrCreateKey(); final Signature signature=Signature.getInstance("Ed25519");
            signature.initSign(pair.getPrivate());
            BiometricPrompt prompt=new BiometricPrompt.Builder(this).setTitle("Confirm recovery authorization")
                    .setSubtitle("Sign one exact receipt; no recovery action will run")
                    .setAllowedAuthenticators(KeyProperties.AUTH_BIOMETRIC_STRONG | KeyProperties.AUTH_DEVICE_CREDENTIAL).build();
            Executor executor=new Executor(){ public void execute(Runnable command){ runOnUiThread(command); }};
            prompt.authenticate(new BiometricPrompt.CryptoObject(signature), new CancellationSignal(), executor,
                new BiometricPrompt.AuthenticationCallback(){
                    @Override public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result){ sign(result,pair); }
                    @Override public void onAuthenticationError(int code, CharSequence message){ state.setText("Not authorized: "+message); }
                });
        } catch (Exception error) { state.setText("Unavailable: secure signing key or device authentication is not available"); }
    }

    private KeyPair loadOrCreateKey() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyPairGenerator generator=KeyPairGenerator.getInstance("Ed25519","AndroidKeyStore");
            generator.initialize(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_SIGN)
                    .setUserAuthenticationRequired(true).setUserAuthenticationParameters(0,
                        KeyProperties.AUTH_BIOMETRIC_STRONG | KeyProperties.AUTH_DEVICE_CREDENTIAL).build());
            generator.generateKeyPair();
        }
        return new KeyPair(store.getCertificate(ALIAS).getPublicKey(), (java.security.PrivateKey)store.getKey(ALIAS,null));
    }

    private void sign(BiometricPrompt.AuthenticationResult result, KeyPair pair) {
        try {
            Signature signature=result.getCryptoObject().getSignature(); long issued=System.currentTimeMillis()/1000L;
            String canonical=RecoveryAuthorizationProtocol.canonicalReceipt(operationId,recordSha,requestSha,workspaceSha,
                    sessionSha,issued,issued+120,"android-keystore:companion-v0",nonce);
            signature.update(canonical.getBytes("UTF-8")); String receipt=RecoveryAuthorizationProtocol.receiptToken(canonical,signature.sign());
            String publicKey=RecoveryAuthorizationProtocol.publicKeyRawBase64(pair.getPublic().getEncoded());
            getSharedPreferences(PREFS,MODE_PRIVATE).edit().putString(RECEIPT_KEY,receipt).putString(PUBLIC_KEY,publicKey).commit();
            state.setText("Authorized once. Receipt expires in 2 minutes; no action was executed.");
        } catch (Exception error) { state.setText("Not authorized: signing failed"); }
    }
    private static String shortId(String value){ return value==null?"invalid":(value.length()<=16?value:value.substring(0,8)+"…"+value.substring(value.length()-8)); }
}
