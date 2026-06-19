# MBclaw ProGuard Rules

# ─── Keep MBclaw classes ──────────────────────────
-keep class com.mbclaw.** { *; }
-keepclassmembers class com.mbclaw.** { *; }

# ─── Chaquopy (Python) ──────────────────────────
-keep class com.chaquo.python.** { *; }
-dontwarn com.chaquo.python.**

# ─── OkHttp ─────────────────────────────────────
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep class okio.** { *; }

# ─── WebSocket ──────────────────────────────────
-keep class org.java_websocket.** { *; }
-dontwarn org.java_websocket.**

# ─── Kotlin ─────────────────────────────────────
-keep class kotlin.** { *; }
-keep class kotlinx.coroutines.** { *; }
-dontwarn kotlinx.coroutines.**

# ─── Gson ───────────────────────────────────────
-keep class com.google.gson.** { *; }
-keepattributes Signature
-keepattributes *Annotation*

# ─── AndroidX ───────────────────────────────────
-keep class androidx.** { *; }
-dontwarn androidx.**

# ─── General ────────────────────────────────────
-keepattributes SourceFile,LineNumberTable
-keepattributes InnerClasses
-keepattributes EnclosingMethod
