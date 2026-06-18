# Shanti Hourly Meditation — **Technical PRD (README)**

Version: 1.1 (Incorporating Additional Concerns v1 and v2)  
Owner: You (Product) • Tech Lead: Agent  
Primary platform: **Android** (robust-by-default).  
Future: iOS portability considered (no compromises on Android).

---

## 0) Executive Summary (What to build)

A small Android app that **plays a bundled 1-minute audio** file `shanti.mp3` **on the hour** for any **user-selected hours** (24 toggles visible; **default ON: 08:00–21:00**).  
Two playback modes:

* **Alarm Mode (default):** play via Alarm stream at **max volume**; intended to sound even under DND (per user’s DND settings for alarms).  
* **Music Mode:** play via Media stream; **respect** DND and current system volume.

The app must be reliable across Doze / app standby / reboot. No network. Minimal UI.

---

## 1) Product Requirements

### 1.1 User Stories

* As a user, I see **24 hour rows** (00–23) with an **On/Off** toggle each.  
* By default, **08–21** are ON; others OFF. I can change any toggle any time.  
* I can switch **Alarm Mode / Music Mode** in Settings.  
* I can enable **Start on Boot** so my schedule survives device restarts (default **ON**).  
* When an enabled hour arrives, the app **plays `shanti.mp3` for ~60s** and stops.  
* The app **keeps working over days** without me needing to reopen it.

### 1.2 Non-Goals

* No custom audio upload.  
* No variable duration (always 1 minute).  
* No in-app volume slider.

### 1.3 Success / Acceptance Criteria

* Hourly playback fires **within ±5s** of top-of-hour on stock Android 12–15 with DND **allowed for alarms** (Alarm Mode).  
* Playback always happens after **reboot** without launching the app.  
* **Doze** and **App Standby** do **not** delay Alarm Mode events (we use exact alarms).  
* Music Mode remains silent if the device is **Muted/DND**.  
* Battery usage: < **0.5% / day** on a modern device with default schedule.

---

## 2) Platform Targets

* **minSdk:** 26 (Android 8.0) — simplifies background rules & services.  
* **targetSdk / compileSdk:** 35 (Android 15).  
* Kotlin + AndroidX; **Jetpack Compose** UI.  
* Audio: `MediaPlayer` (simple, no streaming).  
  (ExoPlayer optional later; not required for a 1-min local file.)

---

## 3) High-Level Architecture

```
app/
 ├─ core/                    (pure Kotlin: scheduling math, hour model, defaults)
 ├─ data/                    (DataStore for prefs: toggles, mode, boot setting)
 ├─ scheduler/               (AlarmManager wrapper + rescheduling logic)
 ├─ playback/                (ForegroundService + MediaPlayer)
 ├─ receivers/               (AlarmReceiver, BootReceiver, TimeChangeReceiver)
 ├─ ui/                      (Compose screens: Hourly list + Settings)
 └─ ShantiApp.kt             (Application: channels, one-time init)
```

**Key flows**

* **Toggle changed →** persist → (re)compute next occurrence(s) → schedule exact alarms (unique `PendingIntent` / hour).  
* **Alarm fires → AlarmReceiver** starts **ForegroundService** → acquire audio focus & wake lock → play `shanti.mp3` (Alarm or Media stream) → stop ~60s → release → schedule next day’s same hour.  
* **BOOT_COMPLETED / TIME_CHANGED / TIMEZONE_CHANGED →** full reschedule from stored prefs.

---

## 4) Data Model

* `Mode`: `ALARM` | `MUSIC` (enum, default `ALARM`)  
* `enabledHours`: `BooleanArray` of size 24 (index = hour 0–23); default true for 8–21.  
* `startOnBoot`: `Boolean` (default true)  
* `lastScheduledEpochMsPerHour`: optional `LongArray` (debug/telemetry, not required)

**Storage:** Jetpack **DataStore (Preferences)** keys:

```
KEY_MODE = "mode" // "ALARM" | "MUSIC"
KEY_HOUR_PREFIX = "hour_" + HOUR_INT  // "hour_0"... "hour_23"
KEY_START_ON_BOOT = "start_on_boot" // bool
```

For direct-boot readiness at reboot (cold boot where user storage may be locked), add a mirrored **Device Protected Storage** (DPS) snapshot for `enabledHours` and `mode` so `BOOT_COMPLETED` can safely reschedule before unlock.  
* Create `BootPrefs` using `createDeviceProtectedStorageContext()` and `SharedPreferences`.  
* On every toggle/mode change (when unlocked), write to both DataStore and `BootPrefs`.  
* In `BootReceiver`, if `!isUserUnlocked()`, read `BootPrefs`; else read DataStore.  
* Optionally handle `ACTION_USER_UNLOCKED` to reschedule once full storage is available.

---

## 5) Permissions & OS Behaviors

**Manifest (platform-scoped; see code below):**

* `SCHEDULE_EXACT_ALARM` (Android 12+ special app-op)  
* `FOREGROUND_SERVICE`  
* `FOREGROUND_SERVICE_MEDIA_PLAYBACK` (Android 14+)  
* `WAKE_LOCK`  
* `RECEIVE_BOOT_COMPLETED`  
* `POST_NOTIFICATIONS` (runtime on Android 13+)  
* `MODIFY_AUDIO_SETTINGS` (to set alarm volume in Alarm Mode, optional but recommended)

**Runtime flows**

* **Exact alarms:** check `AlarmManager.canScheduleExactAlarms()`. If false, deep-link to **Settings “Alarms & reminders”** (ACTION_REQUEST_SCHEDULE_EXACT_ALARM, API 31+).  
* **Notifications:** request **POST_NOTIFICATIONS** (API 33+).  
* **Battery optimization (optional):** present rationale + intent to `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` for problem OEMs. Detect missed fires on problematic OEMs; if 2+ misses in 48h while exact alarms were scheduled, surface a repair card guiding “Ignore battery optimizations” with intent.  
* **DND:** no special permission; Alarm Mode uses Alarm stream / alarm classification. To maximize “sounds under DND” reliability across OEMs:  
  * Use `AudioAttributes(USAGE_ALARM, CONTENT_TYPE_SONIFICATION)`.  
  * For Alarm Mode, add an optional **full-screen intent notification** (CATEGORY_ALARM) that fires with the alarm; make it user-toggleable in Settings (“Show full-screen alarm”). This improves OEM consistency for DND-allowed alarms.  
  * Add a Settings “Open DND settings” deep-link tip describing “Allow alarms in DND”.

**Multi-User Device Support**  
* Behavior on tablets with multiple user profiles: The app should run per profile, with separate DataStore instances.  
* Work profile considerations: Run in both personal and work profiles if installed there.

**Update Migration Path**  
* SharedPreferences → DataStore migration if updating from older version.  
* Schema versioning strategy for future changes (e.g., add a version key to DataStore).

---

## 6) Android Components & Contracts

### 6.1 Notification channels

* `CHANNEL_FOREGROUND` id: `shanti_alarm_fg` • Importance: **LOW**  
  Shown during 1-minute playback; optional persistent status when active.  
  User-visible: NotificationChannel("shanti_alarm_fg", "Meditation Playback", NotificationManager.IMPORTANCE_LOW).apply { description = "Shows when meditation audio is playing"; setShowBadge(false) }  
* `CHANNEL_ERRORS` id: `shanti_alarm_errors` • Importance: DEFAULT  
* `shanti_alarm_alerts` (HIGH, CATEGORY_ALARM) only if full-screen option is enabled for Alarm Mode.

### 6.2 Intents & PendingIntents

* **Alarm PendingIntent (per hour):**  
  `action = "org.shanti.hourly.ACTION_ALARM_HOUR"`  
  extras: `EXTRA_HOUR` (Int 0..23)  
  **requestCode**: `1000 + hour` (unique)  
  flags: `FLAG_UPDATE_CURRENT | FLAG_IMMUTABLE`

* **Service start:** `Context.startForegroundService(...)` from receiver.

### 6.3 Receivers

* `AlarmReceiver` (exported=false): on receive → start `PlaybackService`.  
* `BootReceiver` (exported=true; `BOOT_COMPLETED`): reschedule all enabled hours.  
* `TimeChangeReceiver` (exported=true; `TIME_SET`, `TIMEZONE_CHANGED`): reschedule.

### 6.4 Foreground Service

* `PlaybackService`:  

  * `foregroundServiceType="mediaPlayback"`  
  * State: **Idle → Preparing → Playing → Stopping → Idle**  
  * Audio focus request depending on mode:  
    * Alarm Mode: `USAGE_ALARM`, `CONTENT_TYPE_SONIFICATION`  
    * Music Mode: `USAGE_MEDIA`, `CONTENT_TYPE_MUSIC`  
  * WakeLock: partial (60–70s) or `MediaPlayer.setWakeMode(...)`  
  * On completion/error: stopForeground(true) + stopSelf()  

* Foreground-service start allowances (Android 14/15): Alarms are an **allowed background start reason**, but you must:  
  * Call `startForegroundService()` and then `startForeground()` **within 5 seconds**.  
  * Declare `android:foregroundServiceType="mediaPlayback"` (you did).  
  * Note the system can still rate-limit background FGS starts; our use is sparse (hourly) and user-visible via `setAlarmClock()`, which is compliant.  

> Note: System UI will display only the next upcoming hour in "Next alarm"; all enabled hours remain visible in-app.

* Receiver/Service double-fire guards: Add a lightweight single-instance guard:  
  * Ignore duplicate alarm intents for the same `hour` if they arrive within, say, 5 seconds (some OEMs rebroadcast).  
  * In `PlaybackService`, use an atomic “isPlaying” guard to avoid overlapping starts.  

* Audio Interruption Handling: Add explicit behavior for:  
  - Phone calls during playback (pause/duck/continue?).  
  - Other alarms or priority notifications.  
  - Bluetooth connection/disconnection mid-playback.  
  Use AudioManager.OnAudioFocusChangeListener:  
    when (focusChange) {  
      AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> // pause or continue?  
      AudioManager.AUDIOFOCUS_LOSS -> stopSelfSafely()  
      // etc.  
    }  

* Add AudioFocus handling (AudioManager): transient gain; abandon on stop.  

---

## 7) Scheduling Logic (deterministic)

**Policy**

* Use `AlarmManager` **exact** alarms:  
  * Primary: `setAlarmClock(AlarmClockInfo(...), pendingIntent)` (API 21+) — prefer this for all scheduled hours (user-visible intent) — no special access needed.  
  * Fallbacks by API level:  
    * API 23+: `setExactAndAllowWhileIdle(type=RTC_WAKEUP, triggerAtMillis, pi)`  
    * API 19–22: `setExact(type=RTC_WAKEUP, ...)`  
  * Only show deep-link to **Alarms & reminders** if you fall back to `setExactAndAllowWhileIdle()` on devices where `setAlarmClock()` is undesirable.  
  * **Do not** request `USE_EXACT_ALARM` (reserved category; likely rejected).  

* **Daily reschedule**: When an alarm fires for hour `H`, we **immediately schedule** the **next day’s** `H`. Clarify: `AlarmReceiver` must **check current enabled state** before scheduling next day’s same hour. If the user toggled it OFF after scheduling, do not reschedule.  

**Time compute (local time zone)**

```
now = ZonedDateTime.now()
target = now.withHour(H).withMinute(0).withSecond(0).withNano(0)
if (target.isBefore(now)) target = target.plusDays(1)
triggerAtMillis = target.toInstant().toEpochMilli()
```

**Uniqueness**: requestCode = 1000 + H

---

## 8) Detailed API / Code Skeletons

> *These are reference snippets; production code should follow, with error handling and DI as needed.*

### 8.1 build.gradle (Module)

```gradle
android {
  compileSdk 35
  defaultConfig {
    applicationId "org.shanti.hourly"
    minSdk 26
    targetSdk 35
    versionCode 1
    versionName "1.0"
  }
  buildFeatures { compose true }
  composeOptions { kotlinCompilerExtensionVersion = "1.5.15" }
}

dependencies {
  implementation platform("androidx.compose:compose-bom:2024.10.00")
  implementation "androidx.compose.ui:ui"
  implementation "androidx.compose.material3:material3"
  implementation "androidx.activity:activity-compose:1.9.3"
  implementation "androidx.datastore:datastore-preferences:1.1.1"
  implementation "androidx.core:core-ktx:1.13.1"
}
```

### 8.2 AndroidManifest.xml (key parts)

```xml
<manifest>
  <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />
  <uses-permission android:name="android.permission.WAKE_LOCK" />
  <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
  <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
  <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />

  <application
      android:name=".ShantiApp"
      android:allowBackup="true"
      android:fullBackupContent="@xml/backup_rules"
      android:dataExtractionRules="@xml/data_extraction_rules"
      android:supportsRtl="true">

    <service
        android:name=".playback.PlaybackService"
        android:exported="false"
        android:foregroundServiceType="mediaPlayback" />

    <receiver
        android:name=".receivers.AlarmReceiver"
        android:enabled="true"
        android:exported="false" />

    <receiver
        android:name=".receivers.BootReceiver"
        android:enabled="true"
        android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.BOOT_COMPLETED" />
        <action android:name="android.intent.action.LOCKED_BOOT_COMPLETED" />
      </intent-filter>
    </receiver>

    <receiver
        android:name=".receivers.TimeChangeReceiver"
        android:enabled="true"
        android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.TIME_SET"/>
        <action android:name="android.intent.action.TIMEZONE_CHANGED"/>
      </intent-filter>
    </receiver>

  </application>
</manifest>
```

### 8.3 AlarmScheduler (core scheduling wrapper)

```kotlin
object AlarmScheduler {
    const val ACTION_ALARM_HOUR = "org.shanti.hourly.ACTION_ALARM_HOUR"
    const val EXTRA_HOUR = "extra_hour"
    private const val REQUEST_BASE = 1000

    fun scheduleHour(context: Context, hour: Int) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pi = pendingIntentForHour(context, hour)
        val triggerAt = nextTriggerMillis(hour)

        val info = AlarmManager.AlarmClockInfo(triggerAt, pi)
        am.setAlarmClock(info, pi) // API 21+
    }

    fun cancelHour(context: Context, hour: Int) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        am.cancel(pendingIntentForHour(context, hour))
    }

    fun rescheduleAll(context: Context, enabled: BooleanArray) {
        (0..23).forEach { hour ->
            if (enabled[hour]) scheduleHour(context, hour) else cancelHour(context, hour)
        }
    }

    fun nextTriggerMillis(hour: Int): Long {
        val now = ZonedDateTime.now()
        var t = now.withHour(hour).withMinute(0).withSecond(0).withNano(0)
        if (!t.isAfter(now)) t = t.plusDays(1)
        return t.toInstant().toEpochMilli()
    }

    private fun pendingIntentForHour(ctx: Context, hour: Int): PendingIntent {
        val i = Intent(ctx, AlarmReceiver::class.java).apply {
            action = ACTION_ALARM_HOUR
            putExtra(EXTRA_HOUR, hour)
        }
        return PendingIntent.getBroadcast(
            ctx, REQUEST_BASE + hour, i,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }
}
```

### 8.4 AlarmReceiver → start FG service

```kotlin
class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val hour = intent.getIntExtra(AlarmScheduler.EXTRA_HOUR, -1)

        // Start playback service
        val svc = Intent(ctx, PlaybackService::class.java).apply {
            putExtra(AlarmScheduler.EXTRA_HOUR, hour)
        }
        ContextCompat.startForegroundService(ctx, svc)

        // Schedule next day's same hour
        // (read enabled[] from DataStore if needed and reschedule this hour)
        AlarmScheduler.scheduleHour(ctx, hour)
    }
}
```

### 8.5 PlaybackService (1-minute playback)

```kotlin
class PlaybackService : Service() {
    private var mp: MediaPlayer? = null
    private lateinit var wakeLock: PowerManager.WakeLock

    companion object {
      @Volatile private var playing = false
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
      if (!playing && playStart.tryAcquire()) { /* start */ } else return START_NOT_STICKY
        val mode = SettingsRepo.currentMode() // suspend fun; provide sync snapshot or prefetch
        startForeground(NOTIF_ID, buildNotification())

        acquireWakeLock()
        play(mode)
        return START_NOT_STICKY
    }

    private fun play(mode: Mode) {
        val attrs = AudioAttributes.Builder().apply {
            setContentType(
                if (mode == Mode.ALARM) AudioAttributes.CONTENT_TYPE_SONIFICATION
                else AudioAttributes.CONTENT_TYPE_MUSIC
            )
            setUsage(
                if (mode == Mode.ALARM) AudioAttributes.USAGE_ALARM
                else AudioAttributes.USAGE_MEDIA
            )
        }.build()

        if (mode == Mode.ALARM) setAlarmVolumeToMaxTemporarily()

        mp = MediaPlayer.create(this, R.raw.shanti).apply {
            setAudioAttributes(attrs)
            isLooping = false
            setOnCompletionListener { stopSelfSafely() }
            setOnErrorListener { _, _, _ -> stopSelfSafely(); true }
            start()
        }
    }

    private fun stopSelfSafely() {
        try { mp?.stop() } catch (_: Exception) {}
        try { mp?.release() } catch (_: Exception) {}
        mp = null
        releaseWakeLock()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
        playing = false // release
    }

    private fun buildNotification(): Notification {
        val channelId = "shanti_alarm_fg"
        // ensure channel created in Application
        return NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_meditation)
            .setContentTitle("Shanti Hourly Meditation")
            .setContentText("Playing 1-minute meditation")
            .setOngoing(true)
            .build()
    }

    private fun acquireWakeLock() {
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "shanti:play").apply {
            setReferenceCounted(false); acquire(70_000L)
        }
    }
    private fun releaseWakeLock() { if (this::wakeLock.isInitialized && wakeLock.isHeld) wakeLock.release() }

    override fun onDestroy() {
        mp?.apply {
            if (isPlaying) stop()
            reset()
            release()
        }
        mp = null
        // Cancel any pending handlers
        handler.removeCallbacksAndMessages(null)
    }

    override fun onBind(intent: Intent?) = null
}```

**Volume restore edge cases**: Spell out the algorithm:  
* Capture current alarm volume only if we’re the one changing it.  
* If the user adjusts volume during playback, do **not** clobber their new setting on restore (store a “we-changed-it” flag and original value; restore only when that flag is true and stream volume is unchanged by the user since start).

### 8.6 Compose UI (Hourly toggles)

```kotlin
@Composable
fun HourListScreen(viewModel: ScheduleViewModel) {
    val state by viewModel.uiState.collectAsState()

    LazyColumn {
        items(24) { hour ->
            val label = String.format("%02d:00", hour)
            Row(
                modifier = Modifier.fillMaxWidth().padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(label, style = MaterialTheme.typography.titleMedium)
                Switch(
                    checked = state.enabled[hour],
                    onCheckedChange = { checked -> viewModel.onToggle(hour, checked) }
                )
            }
            Divider()
        }
    }
}
```

### 8.7 Settings Screen

* **Alarm/Music**: Radio buttons or switch.  
* **Start on Boot**: Switch.  
* **Manage Permissions**: Buttons to open:  
  * Notifications permission (API 33+)  
  * Alarms & Reminders (API 31+)  
  * Battery Optimization (optional)  

**UI/UX Specifics**  
* Exact Material3 theme colors/typography.  
* Loading states during permission flows.  
* Empty states / first-run onboarding screens.  
* Confirmation dialogs for destructive actions (if any).  
* Accessibility and internationalization: Respect system 12/24h. Content descriptions for switches, talkback labels (“Enable 08:00 chime”).

**Quick Settings tile (optional, 1 day build)**  
Add a QS tile to toggle **Alarm/Music** quickly or “Pause for today”. Not required, but easy win.

---

## 9) Edge Cases & Policies

* **Force-stop:** System cancels alarms; app can’t auto-restart. Surface a notice on next launch. Add a user-doc note: **Force-stop** cancels alarms; app cannot restart itself (Android platform rule). Show a dismissible in-app banner on next launch.  
* **Time change / TZ change:** reschedule all.  
* **DST transitions:** Using wall-clock `RTC_WAKEUP`; nextTrigger computes next local day. Accept the OS interpretation at cutovers. Add explicit test vectors:  
  * Spring forward: schedule for a missing hour (e.g., 02:00 doesn’t exist) — policy: schedule next valid top-of-hour or skip that day.  
  * Fall back: handle duplicated hour; ensure exactly one fire per enabled hour.  
* **OEM killers:** Offer “Ignore battery optimizations” guidance; still rely on `setAlarmClock()` exact.  
* **DND user settings:** If user disabled **alarms in DND**, Alarm Mode may be muted; we can show an education tip and deep-link to DND settings (view only).  
* **Audio focus conflicts:** For Music Mode, request transient audio focus; for Alarm Mode, we can duck or force alarm stream.  
* **Notification permission denied:** Foreground service still requires a visible notification; app must request it and handle denial (explain: app can’t run correctly without notifications; prompt again with rationale).  
* **Additional Scenarios:** Airplane mode transitions, SIM card removal/insertion, language changes mid-operation, storage full scenarios, rapid time zone changes (crossing borders).  

**Crash Recovery & Error Reporting**  
Since you're offline-only, specify:  
* Local crash log storage mechanism.  
* User-visible error states (what happens if audio file is corrupted?).  
* Fallback behavior if MediaPlayer repeatedly fails (e.g., add error handling (MediaPlayer failures) → fallback retry once).  

**Performance Constraints**  
* Cold start time: < 200ms.  
* Memory usage: < 50MB.  
* Audio latency: start playback within 100ms of trigger.  
* Battery: < 0.5%/day.  
* App size check (<10 MB).  

**Proguard/R8 keep rules**  
Add a small section so shrinker doesn’t strip components:  
```
-keep class org.shanti.hourly.receivers.** { *; }
-keep class org.shanti.hourly.playback.** { *; }
-keepclassmembers class * extends android.app.Service { *; }
-keepclassmembers class * extends android.content.BroadcastReceiver { *; }
```

**Local logging ring buffer**  
Since there’s no network, add a 200-entry in-app log view (timestamped events: schedule/cancel/fire/service start/stop/errors). Great for QA and user support.

---

## 10) iOS Portability Plan (brief)

* Business logic (hours array, defaults, labels) is platform-agnostic.  
* On iOS, use **UNUserNotificationCenter** to schedule **24 daily repeating local notifications** (each top-of-hour).  
  Limitation: custom notification sounds are limited (~30s). Use a short chime on iOS notifications and open the app to play full 60s if user taps. Prepare 30-sec chime variant for iOS notifications.  
* Keep resources portable: reuse `shanti.mp3`.  
* Parallel interfaces:  
  * `ScheduleManager` (Android: AlarmManager; iOS: UNNotificationRequests)  
  * `PlaybackManager` (Android: MediaPlayer; iOS: AVAudioPlayer in foreground)  
* iOS crisp constraints: iOS custom notification sound max ~30s; hourly **background** media playback isn’t permitted. Strategy: schedule notifications with 30s chime; tapping opens app to play full minute via `AVAudioPlayer`. Don’t attempt VoIP or location background modes to keep audio alive; will be rejected.

---

## 11) Telemetry & Logging (local only)

* Optional debug logs around scheduling times, alarm fires, service start/stop.  
* No PII. No network.

---

## 12) QA & Validation Checklist

1. First run:  
   * POST_NOTIFICATIONS prompt (API 33+) → accept/deny paths.  
   * Exact alarm capability (API 31+) → deep-link to grant if needed.  
   * Default schedule 08–21 ON.  
2. Toggle single future hour → fires on time.  
3. Toggle past hour → schedules next day.  
4. Change to Music Mode → DND ON → silent.  
5. Alarm Mode → DND ON with alarms allowed → plays loud.  
6. Reboot device → alarms still fire as per toggles.  
7. TIMEZONE_CHANGED / TIME_SET → correct reschedule.  
8. OEM battery optimization → guidance path tested.  
9. While another media playing → how app behaves per mode.  
10. Long-run test 48h: no drift, no missed hours.  
11. Add explicit test cases for: Airplane mode transitions, SIM card removal/insertion, language changes mid-operation, storage full scenarios, rapid time zone changes (crossing borders).  

**Post-install first-run flow**  
Acceptance test should assert:  
* Request POST_NOTIFICATIONS (API 33+) with rationale.  
* Explain DND behavior and show “Allow alarms in DND” tip.  
* If API 31+ and you’re not using `setAlarmClock()` everywhere, prompt for exact-alarm special access with rationale and deep-link.  

**Developer ops**  
* Add Gradle task aliases and lint/ktlint, and one instrumentation test that boots a `BroadcastReceiver` and asserts service start + notification posted within SLA.

---


- **Killed-service behavior test** — Kill the app process during the 1-minute playback window and verify no auto-restart; next hour plays as scheduled per `START_NOT_STICKY`.
- **Boot/timezone/DST comprehensive test** — With multiple hours toggled, test reboot, timezone change, and (where applicable) DST transitions; confirm in-app schedule persists and system “Next alarm” shows only the next upcoming hour.
- **Android 13+ notifications permission paths** — Validate grant, deny, and deny-forever flows. Ensure Alarm-mode playback never begins without a foreground notification and that the rationale offers Re-prompt and Open Settings.
- **Battery optimization verification** — With and without OEM battery optimizations exemption, verify exact-alarm delivery and FGS continuity; ensure in-app guidance explains exemption steps if alarms are delayed.
## 13) Release & Store

* No internet; add privacy label accordingly.  
* Foreground notification explains purpose: “hourly 1-minute meditation”.  
* Include screens that mirror user’s screenshot style (list + toggles).  
* Update in-app Help (“How Alarm/Music modes behave; DND note; battery tip”).  
* Create Privacy Policy (no data collected).  
* Build **Release** (Proguard/R8 default, shrinker ON).  
* Sign and produce AAB for internal test track.  
* Run acceptance checklist (§12).  
* Prepare Play listing (screenshots of Hour list and Settings).  
* Rollout.

---

## 14) Risks & Mitigations

* **OEM background policies** → rely on `setAlarmClock()` exact alarms + foreground service; provide battery optimization guidance.  
* **User denies notification / exact alarm** → show blocking education dialog with deep-links.  
* **DND policy variations** → document behavior; Alarm Mode depends on user’s DND “Allow alarms”.

---

## 15) Definition of Done

* All Acceptance Criteria met on Android 12, 13, 14, 15 (Google Pixels) + 1–2 OEM devices.  
* No ANRs; no crashes on rotation / background / boot.  
* Startup cold < 200ms to first UI paint.  
* Battery < 0.5% / day at defaults in idle scenario.  
* Ensure service stops within ~70s always (no leaked wakelock).  
* Accessibility labels for toggles, settings.  
* Localize static strings (en).

---

# TASK LIST (Step-by-Step Build Plan)

> **Deliverables:** A working app module; code, resources, tests, and signed release build.

### Phase 0 — Project Setup

1. Create Android project (`minSdk=26`, `target/compile=35`, Kotlin, Compose).  
2. Add dependencies (Compose BOM, DataStore).  
3. Place `shanti.mp3` in `app/src/main/res/raw/shanti.mp3`.  
4. Add app icons, package `org.shanti.hourly`.

### Phase 1 — System Plumbing

5. Create `ShantiApp` `Application` class; initialize **notification channels**.  
6. Define **permissions** in `AndroidManifest` (see §8.2).  
7. Implement **permission helpers**:  
   * POST_NOTIFICATIONS (API 33+).  
   * Exact alarm: check `canScheduleExactAlarms()`, intent to `ACTION_REQUEST_SCHEDULE_EXACT_ALARM` when needed.  
   * Battery optimization prompt (optional).  
8. Implement **DataStore** with defaults (hours 8–21 ON).  
9. Implement **SettingsRepo** (read/write mode, hours, startOnBoot).

### Phase 2 — Scheduler

10. Implement `AlarmScheduler` (as in §8.3).  
11. Implement `AlarmReceiver` (start service + reschedule next day).  
12. Implement `BootReceiver` (BOOT & LOCKED_BOOT) → read DataStore → `rescheduleAll`.  
13. Implement `TimeChangeReceiver` (TIME_SET, TIMEZONE_CHANGED) → `rescheduleAll`.  
14. Write **Unit tests** for `nextTriggerMillis(hour)` across edge cases (past/future, DST sample dates).

### Phase 3 — Playback

15. Implement `PlaybackService` (as in §8.5):  
    * Foreground notification.  
    * MediaPlayer with `AudioAttributes` per mode.  
    * Optional alarm volume max + restore (store old volume).  
    * WakeLock acquire/release.  
16. Add **AudioFocus** handling (AudioManager): transient gain; abandon on stop.

### Phase 4 — UI

17. Compose: `HourListScreen` (24 items + toggles) (see §8.6).  
18. Compose: `SettingsScreen`:  
    * Mode selector (Alarm/Music).  
    * Start on Boot switch.  
    * Buttons: “Allow notifications”, “Allow exact alarms”, “Battery optimization”.  
19. ViewModel (`ScheduleViewModel`):  
    * Expose `enabled[24]`, `mode`, `startOnBoot`.  
    * `onToggle(hour, checked)`: persist then schedule/cancel that hour.  
    * `onModeChanged()`: persist.  
20. Navigation scaffold (two tabs or drawer: “Schedule”, “Settings”).

### Phase 5 — Integration Logic

21. On app first run, ensure:  
    * Create default toggles.  
    * Call `AlarmScheduler.rescheduleAll`.  
22. On toggle change:  
    * If `checked`: `scheduleHour(hour)` else `cancelHour(hour)`.  
23. On **mode** change: no reschedule needed; service picks mode at runtime.  
24. On **startOnBoot** change: stored for BootReceiver gating.

### Phase 6 — Permissions UX

25. When opening app:  
    * If API 33+ and POST_NOTIFICATIONS not granted → show rationale → request.  
26. If API 31+ and `canScheduleExactAlarms()==false` → show screen with CTA to open “Alarms & Reminders”.  
27. Provide “Test now” button to play immediately (debug only, behind a dev toggle).

### Phase 7 — Reliability Hardening

28. Confirm **alarm fires** while app is swiped away (not force-stopped).  
29. Verify **Doze**: adb simulate idle; ensure alarm still fires (Alarm Mode).  
30. Verify **DND** scenarios:  
    * Music Mode muted under DND.  
    * Alarm Mode audible when DND allows alarms.  
31. Reboot test: schedule persists.  
32. OEM test (Samsung/Xiaomi) with and without battery optimization exemption.

### Phase 8 — QA & Polishing

33. Add error handling (MediaPlayer failures) → fallback retry once.  
34. Ensure service stops within ~70s always (no leaked wakelock).  
35. Accessibility labels for toggles, settings.  
36. Localize static strings (en).  
37. App size check (<10 MB).

### Phase 9 — Documentation & Release

38. Update in-app Help (“How Alarm/Music modes behave; DND note; battery tip”).  
39. Create Privacy Policy (no data collected).  
40. Build **Release** (Proguard/R8 default, shrinker ON).  
41. Sign and produce AAB for internal test track.  
42. Run acceptance checklist (§12).  
43. Prepare Play listing (screenshots of Hour list and Settings).  
44. Rollout.

### Phase 10 — (Optional) iOS Prep

45. Extract core constants and hour labels to a shared file.  
46. Draft `ScheduleManager` interface for future iOS implementation notes.  
47. Prepare 30-sec chime variant for iOS notifications.

---

## 16) File/Constant Naming (for Agent)

* Package: `org.shanti.hourly`  
* Channels: `shanti_alarm_fg`, `shanti_alarm_errors`  
* Intent action: `org.shanti.hourly.ACTION_ALARM_HOUR`  
* Extras: `extra_hour`  
* Request codes: `1000 + hour`  
* DataStore keys: `mode`, `hour_0..23`, `start_on_boot`  
* Notification ID: `100`

---

## 17) Testing Commands (developer)

* Force Doze:  
  `adb shell dumpsys deviceidle force-idle`  
* Exit Doze:  
  `adb shell dumpsys deviceidle step` (repeat) or unlock device.  
* Set time quickly:  
  `adb shell date 012312002025.00` (requires root on many devices).  
* DND on/off (UI preferable due to permissions).

---

**Direct Boot check in BootReceiver** (outline):

```kotlin
class BootReceiver : BroadcastReceiver() {
  override fun onReceive(ctx: Context, intent: Intent) {
    val um = ctx.getSystemService(UserManager::class.java)
    val isUnlocked = um?.isUserUnlocked == true
    val source = if (isUnlocked) SettingsRepo(ctx) else BootPrefs(ctx) // DPS-backed
    val state = source.readSnapshot() // blocking/sync read
    AlarmScheduler.rescheduleAll(ctx, state.enabledHours)
  }
}
```

---


## Revision History

- 2025-10-11: Inlined clarifications; set service policy to START_NOT_STICKY in code; removed redundant SharedPreferences note; trimmed addendum to avoid duplication.


- 2025-10-11: Integrated clarifications for service restart policy, DataStore/DPS persistence, setAlarmClock UX note, POST_NOTIFICATIONS acceptance criteria, and QA additions.
- 2025-10-11: Added setAlarmClock system UI note in Section 7; integrated four QA test cases into Section 12.
