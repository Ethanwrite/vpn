@file:Suppress("UnstableApiUsage")

import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

val pkg: String = providers.gradleProperty("amneziawgPackageName").get()
val appId: String = providers.gradleProperty("xingsuiApplicationId").get()
val debugApiBaseUrl: String = providers.gradleProperty("xingsuiDebugApiBaseUrl").orElse("http://10.0.2.2:8000").get()
val releaseApiBaseUrlProvider = providers.gradleProperty("xingsuiReleaseApiBaseUrl")
    .orElse(providers.environmentVariable("XINGSUI_RELEASE_API_BASE_URL"))
val releaseApiBaseUrl: String? = releaseApiBaseUrlProvider.orNull
val requestedTasks = gradle.startParameter.taskNames.joinToString(" ").lowercase()
val needsReleaseApiBaseUrl = listOf("release", "googleplay", "bundle").any { requestedTasks.contains(it) }

if (needsReleaseApiBaseUrl && releaseApiBaseUrl.isNullOrBlank()) {
    throw GradleException("Set -PxingsuiReleaseApiBaseUrl=https://your-api-domain before building a release/googleplay artifact.")
}

fun buildConfigString(value: String): String = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

// Optional release signing driven entirely by Gradle properties or environment
// variables (no secrets in VCS). When the keystore + passwords are absent the
// release build stays unsigned, preserving the previous behaviour.
fun signingValue(propName: String, envName: String): String? =
    providers.gradleProperty(propName).orElse(providers.environmentVariable(envName)).orNull?.takeIf { it.isNotBlank() }

val keystorePath = signingValue("xingsuiKeystoreFile", "XINGSUI_KEYSTORE_FILE")
val keystorePassword = signingValue("xingsuiKeystorePassword", "XINGSUI_KEYSTORE_PASSWORD")
val keystoreAlias = signingValue("xingsuiKeyAlias", "XINGSUI_KEY_ALIAS")
val keyPasswordValue = signingValue("xingsuiKeyPassword", "XINGSUI_KEY_PASSWORD") ?: keystorePassword
val keystoreFile = keystorePath?.let { rootProject.file(it) }
val releaseSigningReady = keystoreFile?.exists() == true && keystorePassword != null && keystoreAlias != null

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.kapt)
}

android {
    buildFeatures {
        buildConfig = true
        dataBinding = true
        viewBinding = true
    }
    namespace = pkg
    defaultConfig {
        applicationId = appId
        targetSdk = 35
        versionCode = providers.gradleProperty("amneziawgVersionCode").get().toInt()
        versionName = providers.gradleProperty("amneziawgVersionName").get()
        buildConfigField("int", "MIN_SDK_VERSION", minSdk.toString())
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }
    if (releaseSigningReady) {
        signingConfigs {
            create("xingsuiRelease") {
                storeFile = keystoreFile
                storePassword = keystorePassword
                keyAlias = keystoreAlias
                keyPassword = keyPasswordValue
                enableV1Signing = true
                enableV2Signing = true
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            manifestPlaceholders["usesCleartextTraffic"] = "false"
            if (releaseSigningReady) {
                signingConfig = signingConfigs.getByName("xingsuiRelease")
            }
            buildConfigField(
                "String",
                "XINGSUI_API_BASE_URL",
                buildConfigString(releaseApiBaseUrl ?: "https://api.xingsui.invalid"),
            )
            proguardFiles("proguard-android-optimize.txt")
            packaging {
                resources {
                    excludes += "DebugProbesKt.bin"
                    excludes += "kotlin-tooling-metadata.json"
                    excludes += "META-INF/*.version"
                }
            }
        }
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            manifestPlaceholders["usesCleartextTraffic"] = "true"
            buildConfigField("String", "XINGSUI_API_BASE_URL", buildConfigString(debugApiBaseUrl))
        }
        create("googleplay") {
            initWith(getByName("release"))
            matchingFallbacks += "release"
        }
    }
    androidResources {
        generateLocaleConfig = true
    }
    lint {
        disable += "LongLogTag"
        warning += "MissingTranslation"
        warning += "ImpliedQuantity"
    }
}

dependencies {
    implementation(project(":tunnel"))
    implementation(libs.androidx.activity.ktx)
    implementation(libs.androidx.annotation)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.constraintlayout)
    implementation(libs.androidx.coordinatorlayout)
    implementation(libs.androidx.biometric)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.fragment.ktx)
    implementation(libs.androidx.preference.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.google.material)
    implementation(libs.zxing.android.embedded)
    implementation(libs.kotlinx.coroutines.android)
    coreLibraryDesugaring(libs.desugarJdkLibs)
}

tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.add("-Xlint:unchecked")
    options.isDeprecation = true
}

tasks.withType<KotlinCompile>().configureEach {
    compilerOptions.jvmTarget.set(JvmTarget.JVM_17)
}
