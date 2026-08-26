package dev.agentbridge.companion;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.SharedPreferences;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyPermanentlyInvalidatedException;
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
    public static final String AUTH_PROFILE_KEY="recovery_authorization_profile";
    public static final String AUTH_PROFILE_EXTRA="authentication_profile";
    private static final String BIOMETRIC_ALIAS="agent_bridge_recovery_authorization_es256_strong_v1";
    private static final String CREDENTIAL_ALIAS="agent_bridge_recovery_authorization_es256_credential_v1";
    private static final String KEY_PROVISIONED_PREFIX="recovery_authorization_key_provisioned_";
    private TextView state;
    private String operationId, recordSha, requestSha, workspaceSha, sessionSha, nonce, authenticationProfile;

    @Override protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        getSharedPreferences(PREFS,MODE_PRIVATE).edit().remove(RECEIPT_KEY).remove(PUBLIC_KEY)
                .remove(AUTH_PROFILE_KEY).commit();
        operationId=getIntent().getStringExtra("operation_id"); recordSha=getIntent().getStringExtra("record_sha256");
        requestSha=getIntent().getStringExtra("request_sha256"); workspaceSha=getIntent().getStringExtra("workspace_sha256");
        sessionSha=getIntent().getStringExtra("session_sha256"); nonce=getIntent().getStringExtra("request_nonce");
        authenticationProfile=getIntent().getStringExtra(AUTH_PROFILE_EXTRA);
        boolean profileValid=true;
        try { RecoveryAuthorizationProtocol.requireAuthenticationProfile(authenticationProfile); }
        catch (IllegalArgumentException error) { profileValid=false; }
        LinearLayout panel=new LinearLayout(this); panel.setOrientation(LinearLayout.VERTICAL); panel.setPadding(32,32,32,32);
        TextView title=new TextView(this); title.setText("Authorize recovery review?"); title.setTextSize(24); panel.addView(title);
        TextView detail=new TextView(this); detail.setText("Action: next\nOperation: "+shortId(operationId)
                +"\nRecord: "+shortId(recordSha)+"\nWorkspace: "+shortId(workspaceSha)
                +"\nAuthentication profile: "+(profileValid?authenticationProfile:"invalid")
                +"\n\nThis signs one exact, short-lived review receipt. It does not execute recovery."); detail.setTextSize(17); panel.addView(detail);
        state=new TextView(this); state.setText(profileValid?"Not authorized":"Unavailable [profile]: explicit supported profile required"); panel.addView(state);
        Button approve=new Button(this); approve.setText("Confirm with device authentication"); panel.addView(approve);
        approve.setEnabled(profileValid);
        Button cancel=new Button(this); cancel.setText("Cancel"); panel.addView(cancel);
        approve.setOnClickListener(new View.OnClickListener(){ public void onClick(View v){ beginAuthentication(); }});
        cancel.setOnClickListener(new View.OnClickListener(){ public void onClick(View v){ finish(); }}); setContentView(panel);
    }

    private void beginAuthentication() {
        if (android.os.Build.VERSION.SDK_INT < 33) { state.setText("Unavailable: Android 13 or newer required"); return; }
        if (RecoveryAuthorizationProtocol.AUTH_PROFILE_BIOMETRIC_STRONG.equals(authenticationProfile)) {
            beginBiometricAuthentication(); return;
        }
        if (RecoveryAuthorizationProtocol.AUTH_PROFILE_DEVICE_CREDENTIAL.equals(authenticationProfile)) {
            beginCredentialAuthentication(); return;
        }
        state.setText("Unavailable [profile]: explicit supported profile required");
    }

    private void beginBiometricAuthentication() {
        try {
            BiometricManager manager=getSystemService(BiometricManager.class);
            if (manager == null || manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                    != BiometricManager.BIOMETRIC_SUCCESS) {
                state.setText("Unavailable [biometric-strong]: configured profile capability is absent"); return;
            }
        } catch (RuntimeException error) {
            state.setText("Unavailable [biometric-check]: biometric capability check failed"); return;
        }
        final KeyPair pair;
        try { pair=loadOrProvisionKey(BIOMETRIC_ALIAS, authenticationProfile, 0, KeyProperties.AUTH_BIOMETRIC_STRONG); }
        catch (Exception error) { state.setText("Unavailable [key-load]: explicit signer reset and repin required"); return; }
        final Signature signature;
        try {
            signature=Signature.getInstance("SHA256withECDSA");
            signature.initSign(pair.getPrivate());
        } catch (KeyPermanentlyInvalidatedException error) {
            state.setText("Unavailable [key-invalidated]: explicit signer reset and repin required"); return;
        } catch (Exception error) {
            state.setText("Unavailable [key-init]: explicit signer reset and repin required"); return;
        }
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
        try {
            BiometricManager manager=getSystemService(BiometricManager.class);
            KeyguardManager keyguard=getSystemService(KeyguardManager.class);
            if (manager == null || manager.canAuthenticate(BiometricManager.Authenticators.DEVICE_CREDENTIAL)
                    != BiometricManager.BIOMETRIC_SUCCESS || keyguard == null || !keyguard.isDeviceSecure()) {
                state.setText("Unavailable [device-credential]: configured profile capability is absent"); return;
            }
        } catch (RuntimeException error) {
            state.setText("Unavailable [credential-check]: device credential capability check failed"); return;
        }
        try {
            BiometricPrompt prompt=new BiometricPrompt.Builder(this).setTitle("Confirm recovery authorization")
                    .setSubtitle("Use the device PIN, pattern, or password to sign one exact receipt")
                    .setAllowedAuthenticators(BiometricManager.Authenticators.DEVICE_CREDENTIAL).build();
            Executor executor=new Executor(){ public void execute(Runnable command){ runOnUiThread(command); }};
            prompt.authenticate(new CancellationSignal(), executor, new BiometricPrompt.AuthenticationCallback(){
                @Override public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                    try {
                        KeyPair pair=loadOrProvisionKey(CREDENTIAL_ALIAS,authenticationProfile,15,KeyProperties.AUTH_DEVICE_CREDENTIAL);
                        Signature signature=Signature.getInstance("SHA256withECDSA"); signature.initSign(pair.getPrivate());
                        sign(signature,pair);
                    } catch (KeyPermanentlyInvalidatedException error) {
                        state.setText("Not authorized [key-invalidated]: explicit signer reset and repin required");
                    } catch (Exception error) {
                        state.setText("Not authorized [credential-sign]: explicit signer reset and repin required");
                    }
                }
                @Override public void onAuthenticationError(int code, CharSequence message){ state.setText("Not authorized: "+message); }
            });
        } catch (RuntimeException error) { state.setText("Unavailable [credential-prompt]: device credential prompt could not start"); }
    }

    private KeyPair loadOrProvisionKey(String alias, String profile, int validitySeconds, int authenticationType) throws Exception {
        RecoveryAuthorizationProtocol.requireAuthenticationProfile(profile);
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        SharedPreferences preferences=getSharedPreferences(PREFS,MODE_PRIVATE);
        String provisionedKey=KEY_PROVISIONED_PREFIX+profile;
        if (!store.containsAlias(alias)) {
            if (preferences.getBoolean(provisionedKey,false))
                throw new IllegalStateException("signer key disappeared; reset and repin required");
            KeyPairGenerator generator=KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC,"AndroidKeyStore");
            KeyGenParameterSpec.Builder spec=new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_SIGN)
                    .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .setUserAuthenticationRequired(true).setUserAuthenticationParameters(validitySeconds,
                        authenticationType).setInvalidatedByBiometricEnrollment(
                            RecoveryAuthorizationProtocol.AUTH_PROFILE_BIOMETRIC_STRONG.equals(profile));
            generator.initialize(spec.build());
            generator.generateKeyPair();
        }
        if (!preferences.edit().putBoolean(provisionedKey,true).commit())
            throw new IllegalStateException("signer provisioning marker unavailable");
        if (store.getCertificate(alias)==null || store.getKey(alias,null)==null)
            throw new IllegalStateException("signer key unavailable");
        return new KeyPair(store.getCertificate(alias).getPublicKey(), (java.security.PrivateKey)store.getKey(alias,null));
    }

    private void sign(Signature signature, KeyPair pair) {
        try {
            long issued=System.currentTimeMillis()/1000L;
            String canonical=RecoveryAuthorizationProtocol.canonicalReceipt(operationId,recordSha,requestSha,workspaceSha,
                    sessionSha,issued,issued+120,"android-keystore:companion-v0",nonce);
            signature.update(canonical.getBytes("UTF-8")); String receipt=RecoveryAuthorizationProtocol.receiptToken(canonical,signature.sign());
            String publicKey=RecoveryAuthorizationProtocol.publicKeyBase64(pair.getPublic().getEncoded());
            RecoveryAuthorizationProtocol.requireAuthenticationProfile(authenticationProfile);
            boolean stored=getSharedPreferences(PREFS,MODE_PRIVATE).edit().putString(RECEIPT_KEY,receipt)
                    .putString(PUBLIC_KEY,publicKey).putString(AUTH_PROFILE_KEY,authenticationProfile).commit();
            if (!stored) throw new IllegalStateException("receipt export unavailable");
            state.setText("Authorized once. Receipt expires in 2 minutes; no action was executed.");
        } catch (Exception error) { state.setText("Not authorized: signing failed"); }
    }
    private static String shortId(String value){ return value==null?"invalid":(value.length()<=16?value:value.substring(0,8)+"…"+value.substring(value.length()-8)); }
}
