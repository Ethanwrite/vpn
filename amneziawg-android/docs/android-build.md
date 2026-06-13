# Android build setup

The project needs JDK 17 and Android SDK/NDK.

Current JDK path on this machine:

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export GRADLE_USER_HOME=/Users/a1-6/vpn/.gradle-home
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export ANDROID_SDK_ROOT=$ANDROID_HOME
export PATH=/opt/homebrew/opt/coreutils/libexec/gnubin:$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:/opt/homebrew/bin:$PATH
export PATH=/opt/homebrew/opt/postgresql@17/bin:$PATH
```

After Android SDK is installed, create `local.properties` in the repo root:

```properties
sdk.dir=/opt/homebrew/share/android-commandlinetools
```

Then build:

```bash
./gradlew :ui:assembleDebug
```

Debug builds use `http://10.0.2.2:8000` by default so the Android emulator can reach the local backend. Override it when needed:

```bash
./gradlew :ui:assembleDebug -PxingsuiDebugApiBaseUrl=http://10.0.2.2:8000
```

Release and Google Play artifacts must provide a real HTTPS API endpoint. The build intentionally fails without this value so a production APK cannot accidentally point at the local dev backend. Release builds also disable cleartext HTTP traffic through the manifest placeholder:

```bash
./gradlew :ui:assembleRelease -PxingsuiReleaseApiBaseUrl=https://api.your-domain.example
```

If Android Studio is used, install:

- Android SDK Platform 35
- Android SDK Build-Tools
- Android NDK
- CMake
