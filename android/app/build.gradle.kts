plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.mbclaw.assistant"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.mbclaw.assistant"
        minSdk = 31  // Android 12+, HyperOS 兼容
        targetSdk = 35
        versionCode = 100
        versionName = "1.0.0-beta"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // Chaquopy Python 配置
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }

        python {
            buildPython("/usr/bin/python3")
            pip {
                install("fastapi==0.115.0")
                install("uvicorn==0.30.0")
                install("sqlalchemy==2.0.36")
                install("chromadb==0.5.23")
                install("httpx==0.28.1")
                install("jieba==0.42.1")
                install("websockets==13.0")
            }
            staticProxy("com.mbclaw.agent.MBclawAgent")
        }
    }

    signingConfigs {
        create("release") {
            storeFile = file(project.findProperty("STORE_FILE") as String)
            storePassword = project.findProperty("STORE_PASSWORD") as String
            keyAlias = project.findProperty("KEY_ALIAS") as String
            keyPassword = project.findProperty("KEY_PASSWORD") as String
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            signingConfig = signingConfigs.getByName("release")
        }
        debug {
            isDebuggable = true
            applicationIdSuffix = ".debug"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
}

dependencies {
    // AndroidX
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.constraintlayout:constraintlayout:2.2.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")

    // Material Design 3
    implementation("com.google.android.material:material:1.12.0")

    // Networking
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // WebSocket
    implementation("org.java-websocket:Java-WebSocket:1.5.7")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // Security (Android Keystore)
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // JSON
    implementation("com.google.code.gson:gson:2.11.0")

    // Testing
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
}
