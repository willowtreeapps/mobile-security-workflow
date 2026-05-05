# Mobile DAST — AI-Guided Workflow

> Successor to the **MobReaper / mobile-security-workflow** Python framework.
> Whereas the legacy tool required hand-coded `mapping.py` + `manager.py` + `vulnerability_service.py` modules per app and only detected 7 fixed issues, this workflow drops the per-app code entirely. Claude acts as the operator: it reasons over the live device, the decompiled APK, and the captured traffic and decides which OWASP MASTG tests to run, in which order, and how to prove (or rule out) each finding.

This file is the contract between the user and Claude. When the user provides a target package and (optionally) a functionality to assess, Claude executes the workflow below autonomously, only asking the user for input when something genuinely cannot be inferred.

---

## 1. Mission & Operating Principles

1. **Act as an expert mobile penetration tester.** Combine static recon, runtime instrumentation, UI driving, and traffic capture to find, exploit and prove vulnerabilities.
2. **Genymotion only.** Always target the Genymotion emulator at `127.0.0.1:6555`. Never attempt to connect to a physical device or another emulator type.
3. **MASTG-aligned.** Every test maps to one or more OWASP MASTG categories (`MASVS-STORAGE`, `MASVS-CRYPTO`, `MASVS-AUTH`, `MASVS-NETWORK`, `MASVS-PLATFORM`, `MASVS-CODE`, `MASVS-RESILIENCE`, `MASVS-PRIVACY`). Reference: <https://mas.owasp.org/MASTG/tests/>.
4. **Evidence-first.** Every finding requires reproducible evidence — the exact command(s), the raw output, a screenshot, and (where applicable) the captured request/response. Findings without evidence are not reported.
5. **Quality over quantity.** Do not invent issues. If a test is inconclusive, mark it `Suspected` and keep digging — do not promote it to a finding.
6. **Autonomous-by-default.** Only ask the user to clarify when the gap is genuine (e.g., need credentials to test post-login functionality, multiple plausible packages match the app name). Never ask the user to perform a manual step Claude can perform itself.
7. **Don't be lazy.** Static recon → dynamic exercise → cross-validation. If the first hook didn't fire, find a different one. If the first traffic capture was empty, instrument harder. The user has explicitly granted time.
8. **Functionality-targeted assessment.** When the user names a functionality (e.g., `Login`), prioritize and weight tests around that flow first, then expand outward to whole-app tests.

---

## 2. Inputs — What The User Provides

The user provides a short brief at kickoff. Claude must accept either form:

```
Package: com.andro.goat
Functionality: Login
```

```
App: AndroGoat
Functionality: PIN setup
```

```
Package: owasp.sat.agoat
```

Resolution rules:

- If the user gives an **app name** (not a package), Claude resolves it to a package by:
  1. `mobile_list_apps` (mobile-mcp) — match by display name.
  2. `adb -s 127.0.0.1:6555 shell pm list packages -f` — match by `.apk` filename or substring.
  3. If multiple matches survive, present the list and ask the user to pick. Otherwise proceed.
- If the user does **not** provide a functionality, treat the brief as "whole-app assessment" — exercise the launcher activity plus every reachable surface (login, registration, settings, deep links).
- The APK is **assumed already installed** on the emulator and **already pulled** to `${DAST_HOME}/apks/<app>.apk` if available. If not pulled, Claude pulls it as part of Phase 2.

### 2.1 Credentials — `.env` file (optional)

Whenever a flow needs credentials (login, registration, PIN, OTP, biometric fallback, etc.), Claude **first** looks for a `.env` file at:

```
${DAST_HOME}/.env    # i.e. the .env in the root of this repository
```

If present, it is loaded once at the start of Phase 0 and the values are reused for the entire session. Recognised keys:

| Key         | Purpose                                                      | Example                 |
| ----------- | ------------------------------------------------------------ | ----------------------- |
| `USER_NAME` | Username / handle for forms that take a non-email identifier | `pentester01`           |
| `EMAIL`     | Email address for login / registration                       | `pentester@example.com` |
| `PASSWORD`  | Password to use in login flows                               | `Sup3rS3cret!`          |

Optional extras Claude will respect if present (do not invent them — only use what's in the file):

| Key            | Purpose                                                                                         |
| -------------- | ----------------------------------------------------------------------------------------------- |
| `PIN`          | Numeric PIN for apps that gate features behind a PIN                                            |
| `OTP`          | Static OTP for test environments that accept a fixed code                                       |
| `PHONE`        | Phone number for SMS-based flows                                                                |
| `API_BASE_URL` | Override for the backend host when the app talks to a staging URL                               |
| `CARD_NUMBER`  | Payment card PAN for testing checkout / payment flows in financial apps (use test card numbers) |
| `CARD_CVV`     | Card verification value (3–4 digits) for payment form flows                                     |
| `CARD_EXPIRY`  | Card expiry date in `MM/YY` format for payment form flows                                       |
| `EXTRA_*`      | Any additional `EXTRA_<NAME>=<value>` pair Claude can substitute into form fields by name match |

Loading rule (run from `mcp-cli-exec` at the start of Phase 0):

```bash
ENV_FILE="${DAST_HOME}/.env"   # DAST_HOME set in Phase 0 from workspace location
if [ -f "${ENV_FILE}" ]; then
  set -a; . "${ENV_FILE}"; set +a
  echo "[+] Loaded credentials from ${ENV_FILE} (keys: $(grep -oE '^[A-Z_][A-Z0-9_]*' "${ENV_FILE}" | tr '\n' ' '))"
else
  echo "[-] No .env file — Claude will pause to ask the user if a credential is needed"
fi
```

Behavioural rules tied to `.env`:

1. **`.env` first, prompt second.** Claude only asks the user for a credential after confirming the relevant key is missing from `.env`. If `EMAIL` and `PASSWORD` are both present, Claude proceeds with the login flow without interrupting.
2. **Credential values may appear in chat and reports.** When narrating progress (e.g., "filling Email field"), Claude may state the value being used. Credential values loaded from `.env` are included verbatim in evidence outputs, findings.json, and the printed report — no redaction is applied.
3. **No redaction policy.** Credential values and sensitive data from `.env` are NOT redacted in the report (§9), the per-finding evidence excerpts, the `INDEX.txt`, or the consolidated transcripts in `${EVIDENCE_DIR}/traffic/full_transcript.txt`. All values appear as-is in all outputs.
4. **`.env` is never copied into evidence.** Do not `cp .env` into `${EVIDENCE_DIR}`. Reference it by path only.
5. **Do not commit `.env`.** Git-ignored by convention; Claude will warn if it sees `.env` staged anywhere it shouldn't be.
6. **Per-app overrides.** If a per-app file exists at `${DAST_HOME}/.env.<package>` (e.g., `.env.owasp.sat.agoat`), Claude loads it **after** the base `.env` and lets it override the shared keys.

If no `.env` exists and a credential is genuinely required to proceed (e.g., a real user/password is needed to test post-login storage), Claude asks once for the missing keys and offers to write them into `.env` for the user — only writing if the user explicitly says yes.

---

## 3. Tool Routing — Which MCP For Which Job

Strict separation of concerns. Pick the right tool the first time.

| Job                                                                                                                              | Tool                                                                                                     | Examples                                                                                            |
| -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Decompile APK; list classes; read Java source; search for strings/methods; inspect AndroidManifest                               | **jadx-mcp-server**                                                                                      | Find `isRooted`, `CertificatePinner`, hardcoded URLs, exported activities, deep-link schemes        |
| Drive the emulator UI; list on-screen elements; tap by text/role; type text; swipe; take screenshots; orientation                | **mobile-mcp**                                                                                           | Walk the login flow, fill credentials, capture each screen as evidence                              |
| Hook & instrument the running process; bypass root/SSL detection; trace crypto calls; dump in-memory state; modify return values | **frida** (via `python3.12` scripts driven by `mcp-cli-exec`, plus `mcp__frida__*` tools when available) | Hook `Cipher.doFinal`, `SharedPreferences.Editor.putString`, `WebView.loadUrl`, custom `isRooted()` |
| Mac-side shell, adb, mitmproxy lifecycle, sqlite3, openssl, file pulls, logcat, dumpsys                                          | **mcp-cli-exec**                                                                                         | `adb shell run-as`, `mitmdump -r`, `sqlite3 file.db`, `openssl x509`, `unzip -p base.apk`           |
| Verify and render Mermaid evidence diagrams                                                                                      | `mcp__c7223339-2579-44fa-a72a-a9878f959524__validate_and_render_mermaid_diagram`                         | (Optional) attack-flow visuals in the report                                                        |

Hard rules:

- **Never** type into the emulator with `adb shell input text` when `mobile-mcp` can do it — `mobile-mcp` types via accessibility and is far more reliable for password fields.
- **Never** tap by hard-coded `x y` coordinates from the legacy MobReaper "Screen Coordinates" workflow. The new flow uses `mobile_list_elements_on_screen` to discover targets, then `mobile_click_on_screen_at_coordinates` with **runtime-resolved** coordinates. Coordinates change between Genymotion device profiles; resolved-at-runtime coordinates do not.
- **Never** edit code or settings outside `${DAST_HOME}/` (this repository). Frida scripts go in `scripts/`, evidence in `evidence/<session-id>/`, pulled apks in `apks/`.

---

## 4. Environment Baseline

| Component                      | Value                                                                                          |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| Emulator                       | Genymotion (`127.0.0.1:6555`)                                                                  |
| Mac proxy IP                   | `192.168.7.3` (recompute each run with `ipconfig getifaddr en0`)                               |
| mitmproxy port                 | `8080`                                                                                         |
| frida-server path on device    | `/data/local/tmp/frida-server`                                                                 |
| mitmproxy CA hash              | `c8750f0d` (recompute with `openssl x509 -subject_hash_old`)                                   |
| Python with Frida              | `python3.12`                                                                                   |
| Capture output                 | `/tmp/mitm.log`, `/tmp/capture.flow`                                                           |
| `DAST_HOME`                    | Absolute path to this repository — resolved at Phase 0 from the workspace location (see below) |
| Working dir                    | `${DAST_HOME}/`                                                                                |
| Frida scripts                  | `${DAST_HOME}/scripts/`                                                                        |
| Pulled APKs                    | `${DAST_HOME}/apks/`                                                                           |
| Evidence                       | `${DAST_HOME}/evidence/<YYYY-MM-DD_HHMM>_<package>/`                                           |
| Credentials (optional)         | `${DAST_HOME}/.env` (see §2.1)                                                                 |
| Per-app credentials (optional) | `${DAST_HOME}/.env.<package>`                                                                  |

The infrastructure setup (mitm install, proxy config, system-CA install, frida-server start) is **identical** to the legacy workflow and is preserved verbatim in §11 — it is plumbing, not the testing logic.

### 4.1 Repository Structure

```
mobile-dast/
├── .env                          # Local credentials — NOT committed (see .env-sample)
├── .env.<package>                # Per-app credential overrides — NOT committed
├── .env-sample                   # Committed template — copy to .env and fill values
├── .gitignore                    # Excludes .env, apks/, evidence/, assets/
├── CLAUDE.md                     # This file — workflow contract
│
├── assets/                       # Report branding assets (logos, cover hero)
│   ├── telus-digital-logo.png
│   ├── telus-digital-logo-black.png
│   └── cover-hero.png
│
├── apks/                         # Pulled APKs — one per target package
│   └── <package>.apk
│
├── scripts/                      # Reusable Frida hooks + report generator
│   ├── generate_report.py        # PDF report generator (WeasyPrint + Jinja2)
│   ├── findings_schema.json      # findings.json schema reference
│   ├── ssl_bypass.py             # Universal SSL pinning bypass
│   ├── root_bypass.py            # Generic root detection bypass template
│   ├── crypto_inspect.py         # Cipher / key / IV hook
│   ├── prefs_writer.py           # SharedPreferences write hook
│   ├── webview_trace.py          # WebView URL + JS interface hook
│   ├── clip_trace.py             # Clipboard copy hook
│   ├── intent_dump.py            # startActivity / sendBroadcast hook
│   └── <app>_<hook>.py           # Per-app one-off scripts (not reused)
│
├── evidence/                     # Session evidence — NOT committed
│   └── <YYYY-MM-DD_HHMM>_<package>/
│       ├── findings.json         # Structured findings (input to generate_report.py)
│       ├── INDEX.txt             # Full artifact listing (find -type f | sort)
│       ├── static/               # jadx outputs, manifest, recon.md
│       │   ├── AndroidManifest.xml
│       │   ├── strings_keys.xml
│       │   └── recon.md
│       ├── dynamic/              # Runtime artifacts
│       │   ├── shared_prefs/     # Pulled SharedPreferences XML files
│       │   ├── databases/        # Pulled SQLite DBs
│       │   ├── logcat.txt        # Full logcat capture
│       │   └── window_dump.txt   # dumpsys window windows
│       ├── frida/                # Per-hook log files + merged all.log
│       ├── screenshots/          # Sequential PNG screenshots (NNN_description.png)
│       ├── traffic/              # mitmproxy artifacts
│       │   ├── capture.flow      # Raw mitmproxy flow file
│       │   ├── mitm.log          # mitmproxy console log
│       │   └── full_transcript.txt
│       └── <SESSION>_report.pdf  # Final PDF report
│
└── jadx-mcp-server/              # jadx MCP bridge (git submodule / clone)
```

---

## 5. The Autonomous Run — Top-Level Loop

When the user provides a brief, Claude executes these phases in order. Each phase has a hard exit condition; if it cannot be met, Claude stops and reports the blocker rather than continuing on bad foundations.

```
Phase 0  Preflight & Session Setup        (skip subsystems already healthy)
Phase 1  Target Resolution                (app name → package → PID)
Phase 2  Static Recon (jadx)              (manifest, classes, strings, attack surface)
Phase 3  Instrumentation Prep             (decide root/SSL bypass needs from Phase 2)
Phase 4  Functional Path Discovery        (drive UI to / through the named functionality)
Phase 5  MASTG Test Loops                 (run categories §7 in order, with evidence)
Phase 6  Evidence Consolidation           (organise files, redact secrets if any captured)
Phase 7  Report                           (print to chat — see §9)
```

Phases 2 and 4 produce a **target list** that drives Phase 5: e.g. "the app uses OkHttp + a custom CertificatePinner subclass, exports a `MainActivity` with a `myapp://` deep link, stores `auth_token` in SharedPreferences, and uses `AES/CBC/PKCS5Padding`". The MASTG loops then go after exactly those things.

---

## 6. Phase Detail

### Phase 0 — Preflight & Session Setup

Run the existing preflight checks (§11 Step 0) and skip subsystems already healthy. Then:

```bash
# Resolve DAST_HOME — the directory containing this CLAUDE.md file.
# Claude knows this from the workspace location; substitute the actual absolute path.
# Example: DAST_HOME="/Users/alice/projects/mobile-security-workflow"
#          DAST_HOME="/opt/security/mobile-dast"
DAST_HOME="<absolute-path-to-this-repo>"   # ← Claude fills this in from the workspace location

SESSION="$(date +%Y-%m-%d_%H%M)_${PACKAGE//./_}"
EVIDENCE_DIR="${DAST_HOME}/evidence/${SESSION}"
mkdir -p "${EVIDENCE_DIR}"/{static,dynamic,traffic,screenshots,frida,artifacts}
echo "Session: ${SESSION}"
echo "Evidence dir: ${EVIDENCE_DIR}"
```

Exit condition: mitmdump up, proxy set on emulator, system CA installed (hash file present), frida-server running, evidence dir writable.

### Phase 1 — Target Resolution

```bash
# 1a. Confirm install
adb -s 127.0.0.1:6555 shell pm list packages | grep -i "${PACKAGE_OR_NAME_FRAGMENT}"

# 1b. Locate the APK on device
adb -s 127.0.0.1:6555 shell pm path "${PACKAGE}"

# 1c. Pull the APK if not already in apks/
adb -s 127.0.0.1:6555 pull <path-from-1b> ${DAST_HOME}/apks/${PACKAGE}.apk

# 1d. Find the launchable activity (used in Phase 4)
adb -s 127.0.0.1:6555 shell cmd package resolve-activity --brief "${PACKAGE}" | tail -1
```

If the user gave an app name (not package), reconcile via `mobile_list_apps` first.

### Phase 2 — Static Recon (jadx-mcp-server)

Open the pulled APK in JADX-GUI (`open -a jadx-gui ${DAST_HOME}/apks/${PACKAGE}.apk`) and let the user know it's loading. Then drive the recon via `mcp__jadx-mcp-server__*` tools.

Static recon checklist — produce a written **Recon Report** at the end of Phase 2 capturing:

| Question                                                                       | jadx-mcp-server tool                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ----- | --- | ------ | -------- | ---- | ------------- |
| What is the package, version, minSdk, targetSdk, debuggable flag?              | `get_android_manifest`                                                                                                                                                                                                                                                                                     |
| What permissions are requested?                                                | `get_android_manifest`                                                                                                                                                                                                                                                                                     |
| Which activities/services/receivers/providers are **exported**?                | `get_android_manifest` + filter `android:exported="true"`                                                                                                                                                                                                                                                  |
| What deep-link schemes/hosts/paths are declared?                               | search manifest for `<intent-filter>` with `android:scheme`                                                                                                                                                                                                                                                |
| Is there a `network_security_config.xml`? Cleartext allowed? Pinning declared? | `get_resource_file` for `xml/network_security_config.xml`                                                                                                                                                                                                                                                  |
| What classes implement root detection?                                         | `search_classes_by_keyword` for `Root`, `SafetyNet`, `isRooted`, `RootBeer`, `Magisk`, `superuser`, `/system/xbin/su`                                                                                                                                                                                      |
| What classes do SSL pinning?                                                   | `search_classes_by_keyword` for `CertificatePinner`, `TrustManager`, `X509TrustManager`, `pinning`, `OkHttpClient.Builder.certificatePinner`                                                                                                                                                               |
| What crypto APIs are used?                                                     | `search_method_by_name` for `Cipher.getInstance`, `MessageDigest.getInstance`, `Mac.getInstance`, `KeyGenerator`, `SecretKeySpec`, `IvParameterSpec`                                                                                                                                                       |
| Where are credentials/tokens read or written?                                  | `search_classes_by_keyword` for `SharedPreferences`, `getSharedPreferences`, `EncryptedSharedPreferences`, `KeyStore.getInstance`                                                                                                                                                                          |
| Hardcoded secrets?                                                             | `get_strings` then grep `(?i)(api[_-]?key                                                                                                                                                                                                                                                                  | secret | token | aws | bearer | password | jdbc | card[_-]?number | cvv | pan | http[s]?://)` — for financial apps also scan for 13–19 digit sequences matching Luhn (potential hardcoded PANs) |
| Is WebView used? `setJavaScriptEnabled`? `addJavascriptInterface`?             | `search_method_by_name` for `setJavaScriptEnabled`, `addJavascriptInterface`, `loadUrl`, `loadDataWithBaseURL`                                                                                                                                                                                             |
| Are there `Log.*` calls in release?                                            | `search_method_by_name` for `Log.d`, `Log.v`, `Log.i`, `Log.e`, `printStackTrace`                                                                                                                                                                                                                          |
| Native libs / dynamic class loading?                                           | `search_method_by_name` for `System.loadLibrary`, `DexClassLoader`, `PathClassLoader`                                                                                                                                                                                                                      |
| Is this a React Native / Expo / Hermes app?                                    | Check APK for `assets/index.android.bundle` or `assets/index.android.bundle.hbc` (Hermes bytecode); look for `com.facebook.react`, `expo.*`, `com.swmansion` packages in class list                                                                                                                        |
| Analytics consent flags in manifest?                                           | `get_android_manifest` → grep for `firebase_analytics_collection_enabled`, `firebase_automatic_screen_reporting_enabled`, `firebase_crashlytics_collection_enabled`, `google_analytics_adid_collection_enabled` — `true` at launch = pre-consent data collection                                           |
| `isRooted` / root detection — is it enforcement or telemetry?                  | For every class found by `isRooted` keyword search, call `get_class_source` to confirm the class actually gates app flow (e.g., throws exception, blocks UI) vs. merely reading a field into a data model (Firebase `OsData`, `m6.E`-style). Never report a telemetry field as root-detection enforcement. |

**Mandatory artifact saves after Phase 2** — every item below must land on disk, not just appear in chat:

```bash
EVIDENCE_DIR="<session-evidence-path>"   # set once, use absolute path everywhere

# Manifest
adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} cat /data/data/${PACKAGE}/" 2>/dev/null || true
# Write manifest XML (from jadx get_android_manifest output) to:
# cat > "${EVIDENCE_DIR}/static/AndroidManifest.xml" << 'EOF' ... EOF

# Strings (from jadx get_strings output — grep for secrets/keys)
# cat > "${EVIDENCE_DIR}/static/strings_keys.xml" << 'EOF' ... EOF

# Recon summary
# cat > "${EVIDENCE_DIR}/static/recon.md" << 'EOF' ... EOF
```

Rule: if a static finding (hardcoded key, dangerous flag, exported component) is cited in the report, the raw evidence file must exist in `${EVIDENCE_DIR}/static/` before Phase 7 runs. Evidence that lives only in chat is not evidence.

Save the recon report to `${EVIDENCE_DIR}/static/recon.md`.

### Phase 3 — Instrumentation Prep

Based on the Recon Report, decide which Frida scripts to load **before** Phase 4 starts:

- **Root detection found** → run the root-bypass template (§11 Step 6) with class/method names taken from the Recon Report. Verify the bypass works (app proceeds past the root-check screen).
- **SSL pinning found OR mitm shows TLS handshake failures in Phase 4** → run the SSL-bypass template (§11 Step 7). Re-verify traffic flows after the bypass loads.
  - **If Java-layer SSL hooks load but TLS traffic still doesn't flow through mitm** → the app uses native BoringSSL/Conscrypt (common in OkHttp3 on modern Android, all React Native/Hermes apps). Java `SSLContext.init` / `TrustManagerImpl` hooks are bypassed at the native layer. Escalation path (in order):
    1. Try `frida-server` spawn mode with `--pause` + resume after hooks load.
    2. If spawn mode causes crash (~12s after start) — app has anti-hook logic or the native SSL layer initialises before Java hooks settle. Stop spawn attempts.
    3. Escalate to **APK gadget injection**: `objection patchapk --source ${PACKAGE}.apk` — this embeds `frida-gadget.so` directly; no frida-server needed. Document this as a remediation requirement in the report and mark N-2 / auth tests as `Needs Further Investigation`.
    4. Alternatively, try `objection explore` after attaching, which may catch SSL after process resume.
  - **Java hooks not firing despite successful attach** — run `Java.enumerateLoadedClasses` to confirm the target class is actually loaded before the hook tries to install.
- **React Native / Hermes app detected** → Java-layer Frida hooks for app-level logic **will not fire** — the JS bundle runs inside Hermes VM, not as Java bytecode. Crypto, auth, and storage operations are implemented in JS (or delegated to native modules). Adjust test strategy:
  - Storage: focus on `RKStorage.db` (AsyncStorage) and SharedPrefs populated by native SDK modules (Braze, Firebase, etc.)
  - Crypto: look for crypto native modules (`NativeCrypto`, `react-native-keychain`, `expo-secure-store`)
  - Network: traffic analysis is the primary signal; Frida hooks for OkHttp/Conscrypt still apply at the native networking layer
- **Crypto calls found** → preload the crypto inspector hook (§10) so the very first cipher invocation in Phase 4 is captured.
- **SharedPreferences usage found** → preload the prefs writer hook (§10).
- **WebView found** → preload the WebView tracer hook (§10).

Each loaded hook gets its own log file in `${EVIDENCE_DIR}/frida/`.

### Phase 4 — Functional Path Discovery (mobile-mcp)

The legacy tool's per-app `mapping.py` is replaced by **live UI exploration**. For a functionality-targeted assessment, drive the emulator with `mobile-mcp`:

```
1. mobile_launch_app(packageName=PACKAGE)
2. Take baseline screenshot → ${EVIDENCE_DIR}/screenshots/01_launch.png
3. mobile_list_elements_on_screen → identify the path to <Functionality>
4. For each step on the path:
   a. tap / type / swipe via mobile-mcp
   b. screenshot → ${EVIDENCE_DIR}/screenshots/NN_<step>.png
   c. note any new traffic in /tmp/mitm.log
5. Reach the functionality. Exercise it with both happy-path and abuse inputs:
   - happy path     : valid creds, valid PIN, legitimate file upload
   - abuse path     : empty input, oversize input, SQLi/XSS payloads, special chars,
                      Unicode, repeated attempts (lockout test), backgrounding mid-flow
```

Always capture a screenshot **before** and **after** every state-changing tap. Store them with monotonically-increasing filenames so the report can replay the user journey.

**Injection & abuse-path screenshot rule** — for any injection test (SQLi, OS CMD, XSS, deep-link abuse, etc.) or abuse-path input, capture **three** screenshots in sequence:

1. `<FXX>_a_payload_entered.png` — the payload typed into the field, button not yet pressed.
2. `<FXX>_b_trigger.png` — immediately after pressing RUN / VERIFY / SUBMIT (even if the result takes a moment).
3. `<FXX>_c_result.png` — the screen showing the actual output/response (error message, dumped data, alert, command output, etc.).

If the result appears as a Toast or transient overlay, use `mobile_take_screenshot` immediately after the tap to catch it. A finding that shows the payload entered but **not** the resulting output is incomplete evidence — the result screenshot is mandatory.

If any step asks for credentials, Claude **first** consults the `.env` loaded in Phase 0 (§2.1) and substitutes the matching key (`USER_NAME`, `EMAIL`, `PASSWORD`, `PIN`, `OTP`, `PHONE`, `EXTRA_*`). Only when the required key is genuinely absent from `.env` does Claude pause and ask the user — and even then it offers to persist the answer back into `.env`. This is one of the few legitimate user-input scenarios.

### Phase 5 — MASTG Test Loops

Run the catalog in §7. For each test:

1. **Pre-condition** — verify the test is applicable from the Recon Report. Skip if N/A and note it (e.g., "no SQLite DB exists, skipping MASVS-STORAGE/sqlite tests").
2. **Execute** — run the commands / hooks defined for that test.
3. **Capture evidence** — command, output, screenshot or pcap, into `${EVIDENCE_DIR}`.
4. **Classify** — `Confirmed`, `Likely`, `Suspected`, or `Pass`. Suspected results require deeper investigation before promoting.
5. **Cross-validate** — for `Likely` and above, attempt a second independent confirmation (e.g., a static-source quote alongside a runtime hook log).

### Phase 6 — Evidence Consolidation

**Static artifact completeness check** — before indexing, confirm that every finding cited in Phase 5 has its source artifact on disk. Chat output is NOT evidence. Run this audit:

```bash
# Every finding that cites a static source must have a corresponding file
ls -la "${EVIDENCE_DIR}/static/"       # expect: recon.md, AndroidManifest.xml, strings_keys.xml (at minimum)
ls -la "${EVIDENCE_DIR}/dynamic/"      # expect: shared_prefs/, logcat.txt, window_dump.txt, databases/
ls -la "${EVIDENCE_DIR}/screenshots/"  # expect: sequential NNNxx_*.png files

# If any are missing — write them now using heredoc via mcp-cli-exec, NOT Write tool
# (Write tool cannot write to $HOME/... — use cat heredoc via mcp-cli-exec)
```

```bash
# Index every artifact
find "${EVIDENCE_DIR}" -type f | sort > "${EVIDENCE_DIR}/INDEX.txt"

# Save the merged frida log
cat ${EVIDENCE_DIR}/frida/*.log > "${EVIDENCE_DIR}/frida/all.log" 2>/dev/null || true

# Convert mitm flow to a readable transcript
mitmdump -r /tmp/capture.flow --flow-detail 3 > "${EVIDENCE_DIR}/traffic/full_transcript.txt" 2>&1
mitmdump -r /tmp/capture.flow -s '/dev/null' > /dev/null 2>&1 # validate
cp /tmp/capture.flow "${EVIDENCE_DIR}/traffic/capture.flow"
cp /tmp/mitm.log "${EVIDENCE_DIR}/traffic/mitm.log"
```

Do not redact any values from text dumps, transcripts, or evidence files. All credential values, tokens, and sensitive data appear verbatim in the report, findings.json, and all evidence artifacts.

### Phase 7 — Report

**Step 7a — Write findings.json**

After Phase 6 evidence consolidation, serialise all confirmed and likely findings into a structured JSON file and save it to the evidence directory. Use `mcp-cli-exec` with a heredoc (not the Write tool, which cannot reach `$HOME/...`):

```bash
# Absolute path — mcp-cli-exec variable persistence rule: inline, never split
cat > "${DAST_HOME}/evidence/<SESSION>/findings.json" << 'FINDINGS_EOF'
{
  "target": {
    "name":            "<App display name>",
    "packageName":     "<com.example.app>",
    "versionName":     "<versionName from manifest>",
    "versionCode":     "<versionCode>",
    "androidVersion":  "<Android N (API NN) from emulator>",
    "functionality":   "<Login | All>",
    "startDate":       "<YYYY-MM-DD>",
    "finishDate":      "<YYYY-MM-DD>",
    "sessionEvidence": "${DAST_HOME}/evidence/<SESSION>"
  },
  "environment": "<Development | Production | Staging>",
  "teamName": "TELUS Digital Solutions Security team",
  "findings": [
    {
      "id":         "F-01",
      "title":      "<Short descriptive title>",
      "severity":   "<Critical | High | Medium | Low | Info>",
      "confidence": "<Confirmed | Likely>",
      "masvs":      "<MASVS-STORAGE / S-1>",
      "mastgTest":  "<MASTG-TEST-NNNN — Test name>",
      "cwe":        "<CWE-NNN — Title>",
      "status":     "open",
      "description": "<2-4 sentence technical description>",
      "evidence": [
        {
          "title":   "<Evidence block title>",
          "command": "<verbatim adb/frida/sqlite3 command>",
          "output":  "<trimmed raw output — verbatim, no redaction>"
        },
        {
          "title":          "<Screenshot description>",
          "screenshotPath": "${DAST_HOME}/evidence/<SESSION>/screenshots/<NNN>_<description>.png"
        },
        {
          "title":        "Frida hook log",
          "fridaLogExcerpt": "<relevant lines from frida hook log>"
        },
        {
          "title":      "Source reference (jadx)",
          "jadxSource": "// com.example.ClassName#methodName (line N)\n<offending code>"
        },
        {
          "title":         "Network capture",
          "networkSample": "<HTTP request/response excerpt — verbatim, no redaction>"
        }
      ],
      "remediation": "<Specific, actionable remediation with a reference URL>",
      "references": [
        "https://mas.owasp.org/MASTG/tests/...",
        "https://developer.android.com/..."
      ]
    }
  ]
}
FINDINGS_EOF
echo "[+] findings.json written"
```

**Screenshot naming convention** — name every screenshot with the target finding ID as a prefix so `generate_report.py` can auto-attach it:

```
${EVIDENCE_DIR}/screenshots/F01_shared_prefs.png          → attaches to finding F-01
${EVIDENCE_DIR}/screenshots/F02_mitm_traffic_visible.png  → attaches to finding F-02
${EVIDENCE_DIR}/screenshots/03_login_success.png          → no ID prefix; auto-attaches to first finding
```

A fully worked example with multiple findings is in:

```
${DAST_HOME}/scripts/findings_schema.json
```

**Step 7b — Generate the PDF report**

```bash
# One-time dependency install (skip if already installed)
pip install weasyprint jinja2 --break-system-packages --quiet 2>&1 | tail -3

# Generate — screenshots-dir is auto-detected but shown explicitly for clarity
python3.12 ${DAST_HOME}/scripts/generate_report.py \
  "${DAST_HOME}/evidence/<SESSION>/findings.json" \
  "${DAST_HOME}/evidence/<SESSION>/<SESSION>_report.pdf" \
  --screenshots-dir "${DAST_HOME}/evidence/<SESSION>/screenshots"
```

Expected output:

```
[*] Auto-detected screenshots directory: .../screenshots
[*] Rendering PDF → .../2026-04-28_1121_com_ohlq_app_dev_report.pdf
[+] Report saved: .../2026-04-28_1121_com_ohlq_app_dev_report.pdf
[+] Findings: 5  (Critical: 0  High: 3  Medium: 1  Low: 1)
```

**Step 7c — Print the chat report**

Print the report to chat in the format defined in §9. Tell the user the PDF path. Do **not** create a separate `.md` file unless the user asks for one.

---

## 7. MASTG Test Catalog (Android)

Each entry: **what it tests → which tools → how to execute → what evidence to collect → pass/fail criteria.** Tests are grouped by MASVS category. Test IDs reference the OWASP MASTG (<https://mas.owasp.org/MASTG/tests/>).

### 7.1 MASVS-STORAGE — Data Storage

**S-1. SharedPreferences leak** — _MASTG-TEST: Testing Local Storage for Sensitive Data_

- Tools: `mcp-cli-exec` (adb run-as), `frida` (write-hook), `jadx-mcp-server`
- Execute:

  ```bash
  # List all prefs files
  adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} ls -la /data/data/${PACKAGE}/shared_prefs/"

  # Pull EACH file individually to disk (not just cat to chat — files must land in evidence dir)
  PREFS_DIR="${EVIDENCE_DIR}/dynamic/shared_prefs"
  mkdir -p "${PREFS_DIR}"
  for f in $(adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} ls /data/data/${PACKAGE}/shared_prefs/"); do
    adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} cat /data/data/${PACKAGE}/shared_prefs/${f}" \
      > "${PREFS_DIR}/${f}"
    echo "Saved: ${f}"
  done
  ```

  Plus the `prefs_writer` Frida hook (§10) to catch values _before_ any encryption.

- **React Native / AsyncStorage check** (run whenever RN architecture detected in Phase 2):
  ```bash
  # RKStorage.db is React Native's AsyncStorage backing store
  adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} ls -la /data/data/${PACKAGE}/databases/" | grep -i rkstorage
  adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} cat /data/data/${PACKAGE}/databases/RKStorage.db" \
    > "${EVIDENCE_DIR}/dynamic/RKStorage.db"
  sqlite3 "${EVIDENCE_DIR}/dynamic/RKStorage.db" ".tables"
  # Dump persist:root — contains full Redux store (may include API keys, SDK config, auth tokens)
  sqlite3 "${EVIDENCE_DIR}/dynamic/RKStorage.db" \
    "SELECT value FROM catalystLocalStorage WHERE key='persist:root';" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); [print(k,'=',v[:200]) for k,v in json.loads(d.get('persist:root','{}')).items()]" \
    > "${EVIDENCE_DIR}/dynamic/RKStorage_dump.txt" 2>/dev/null || \
  sqlite3 "${EVIDENCE_DIR}/dynamic/RKStorage.db" ".dump" > "${EVIDENCE_DIR}/dynamic/RKStorage_dump.txt"
  ```
  Fail if `persist:root` or any AsyncStorage key contains API keys, SDK secrets, tokens, or PII in plaintext.
- Evidence: the XML files in `shared_prefs/` subdir on disk, the hook log showing keys with sensitive values written in plaintext, the source-code reference from jadx that wrote them. For RN apps: `RKStorage.db` and `RKStorage_dump.txt`.
- Fail if: passwords, tokens, PII, session IDs, PINs, or **card data** (`CARD_NUMBER`, `CARD_CVV`, `CARD_EXPIRY`) visible without encryption (and the app is not using `EncryptedSharedPreferences`). Card data in plaintext storage is always **Critical** severity regardless of app type.

**S-2. SQLite database leak**

- Execute:
  ```bash
  adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} ls -la /data/data/${PACKAGE}/databases/"
  adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} cat /data/data/${PACKAGE}/databases/<db>" > "${EVIDENCE_DIR}/dynamic/<db>"
  sqlite3 "${EVIDENCE_DIR}/dynamic/<db>" ".tables"
  sqlite3 "${EVIDENCE_DIR}/dynamic/<db>" ".dump"
  ```
- Fail if: plaintext sensitive data; if the file is SQLCipher-encrypted, attempt to extract the key via Frida (hook `SQLiteDatabase.openOrCreateDatabase` or net.sqlcipher equivalents) — if the key is hardcoded or derivable, that is itself a finding.

**S-3. Internal/external file storage**

- Execute:
  ```bash
  adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} ls -laR /data/data/${PACKAGE}/files/ /data/data/${PACKAGE}/cache/"
  adb -s 127.0.0.1:6555 shell ls -laR /sdcard/Android/data/${PACKAGE}/   # external — readable by other apps on older Android
  adb -s 127.0.0.1:6555 shell ls -laR /sdcard/   # any global-readable artifact
  ```
- Fail if: sensitive files written world-readable, or written to `/sdcard/` without explicit user choice.

**S-4. Logs leaking sensitive data** — _MASTG-TEST: Testing Logs_

- Execute (in parallel with Phase 4 functional run):
  ```bash
  adb -s 127.0.0.1:6555 logcat -c
  # ... drive the functionality ...
  adb -s 127.0.0.1:6555 logcat -d > "${EVIDENCE_DIR}/dynamic/logcat.txt"
  grep -iE "password|token|bearer|secret|pin|ssn|cvv|card|email|api[_-]?key" "${EVIDENCE_DIR}/dynamic/logcat.txt"
  ```
- Fail if: any of the regex matches show real input the user just typed.

**S-5. Clipboard exposure**

- Drive the functionality, then:
  ```bash
  adb -s 127.0.0.1:6555 shell service call clipboard 2
  ```
  Hook `android.content.ClipboardManager.setPrimaryClip` with Frida and log every clip copied. Fail if the app copies sensitive data (passwords, OTPs) silently.

**S-6. Backgrounding / screenshot in Recents**

- Drive to a sensitive screen, press home, then:

  ```bash
  # Step 1 — capture the Recents thumbnail (visual proof)
  adb -s 127.0.0.1:6555 shell input keyevent KEYCODE_APP_SWITCH
  adb -s 127.0.0.1:6555 shell screencap -p /sdcard/recents.png
  adb -s 127.0.0.1:6555 pull /sdcard/recents.png "${EVIDENCE_DIR}/screenshots/recents_thumbnail.png"

  # Step 2 — confirm FLAG_SECURE absence via window dump (required disk artifact)
  adb -s 127.0.0.1:6555 shell dumpsys window windows > "${EVIDENCE_DIR}/dynamic/window_dump.txt"
  grep -i "secure\|FLAG_SECURE\|${PACKAGE}" "${EVIDENCE_DIR}/dynamic/window_dump.txt" | head -20
  ```

  The window dump is the authoritative programmatic evidence. `FLAG_SECURE` (hex `0x00002000`) appears in the flags column for the app's window entry when the flag is set. Its absence in the flags string is the finding.

- Fail if: the recents thumbnail still shows sensitive content **and** `FLAG_SECURE` / `SECURE` is absent from the app's window flags in `window_dump.txt`.

**S-7. Auto-backup / adb backup**

- Read the manifest's `android:allowBackup` (jadx) and try:
  ```bash
  adb -s 127.0.0.1:6555 backup -f "${EVIDENCE_DIR}/dynamic/full.ab" "${PACKAGE}"
  ```
- Fail if: backup runs and the resulting `.ab` contains `shared_prefs/`, `databases/` with sensitive data.

### 7.2 MASVS-CRYPTO — Cryptography

**C-1. Weak / deprecated algorithms** — _MASTG-TEST: Testing Symmetric Cryptography_

- Tools: `frida` crypto inspector (§10), `jadx`
- Hook `javax.crypto.Cipher.getInstance(String)` and log every transformation observed at runtime.
- Fail if: `DES`, `RC4`, `MD5`, `SHA1`, `AES/ECB/*`, or `AES/CBC/*` _without_ HMAC.

**C-2. Hardcoded keys / IVs**

- Hook `SecretKeySpec.<init>` and `IvParameterSpec.<init>`; print the byte arrays in hex.
- Cross-reference the key bytes with `get_strings` from jadx.
- Fail if: a key/IV byte array appears verbatim in the APK strings.

**Mandatory evidence for every hardcoded-value finding (keys, tokens, promo codes, passwords, IVs, URLs):**
Never cite `get_strings` output or `strings_keys.txt` as the sole source. Always call `get_class_source` on the class that contains the value and include the **actual decompiled code snippet** showing:

- The class name and method where the value is assigned/compared.
- The hardcoded literal itself in context (assignment, comparison, or return statement).
- Any surrounding logic that shows how the value is used (e.g., client-side `equals()` check, direct `exec()` concatenation).

Example of correct `jadxSource` evidence:

```java
// owasp.sat.agoat.HardCodeActivity#onCreate
final Ref.ObjectRef promoCode = new Ref.ObjectRef();
promoCode.element = "NEW2019";  // hardcoded value
if (promoCodeValue.getText().toString().equals((String) promoCode.element)) {
    priceValue.setText("0");  // product obtained for free
}
```

A `jadxSource` block that says only "value found in strings_keys.txt" or "extracted from get_strings" is **not acceptable** — it will be treated as missing evidence.

**C-3. Insecure randomness**

- Hook `java.util.Random.nextBytes` and `java.util.Random.nextInt` — fail if used in a security context (key/IV/nonce/token generation). Compare with `SecureRandom`.

**C-4. KeyStore protection**

- Hook `java.security.KeyStore.load`, `KeyGenParameterSpec.Builder.setUserAuthenticationRequired`. Fail if user-auth-bound keys are not used for sensitive operations on a device that has a secure lock screen.

**C-5. Custom crypto / "encryption" by string concatenation**

- jadx search for `xor`, `Base64.encodeToString`, `(byte) (... ^ ...)` patterns — manual review required.

### 7.3 MASVS-AUTH — Authentication & Session Management

**A-1. Token storage** — Token must live in EncryptedSharedPreferences or KeyStore-backed storage. Re-use S-1 evidence.

**A-2. Token transmission** — From `/tmp/capture.flow`, every authenticated request must use `Authorization` header over TLS, never URL parameters.

**A-3. Logout invalidates server-side session** — capture token, logout via UI, replay the captured request with the old token via `mitmdump -r ... | curl --data ...` or Burp-style replay. Fail if 200 OK on the post-logout replay.

**A-4. Brute-force / lockout** — drive 10 failed logins via `mobile-mcp`, observe whether the server returns 429 / account-lock or the client implements local rate limiting.

**A-5. Biometric prompt bypass** — if the app uses `BiometricPrompt`, hook `BiometricPrompt$AuthenticationCallback.onAuthenticationSucceeded` and force-call it; fail if the protected functionality activates.

**A-6. MFA / 2FA bypass** — if 2FA exists, attempt to skip the OTP step by replaying the post-OTP request before submitting the OTP. Fail if it succeeds.

### 7.4 MASVS-NETWORK — Network Communication

**N-1. Cleartext HTTP** — search Phase 6 transcript for `http://` requests originating from the app (filter by host). Fail if any.

**N-2. TLS pinning** — initially run mitm **without** the SSL bypass loaded:

- **If traffic flows through mitm → pinning is ABSENT** — this is a **finding** for any app handling sensitive data. Do not treat readable traffic as a pass; treat it as a confirmed lack of pinning and collect evidence immediately:

  ```bash
  # Capture a representative authenticated request as evidence
  mitmdump -r /tmp/capture.flow --flow-detail 3 2>/dev/null \
    | grep -A 20 "Host: <app-backend-host>" \
    > "${EVIDENCE_DIR}/traffic/pinning_absent_sample.txt"

  # Screenshot of mitmproxy showing decrypted traffic
  # Save to ${EVIDENCE_DIR}/screenshots/mitm_traffic_visible.png
  ```

  Severity: **High** for production apps handling auth tokens, PII, or financial data. **Medium** for apps with lower sensitivity. Report as: "Missing Certificate Pinning — MASVS-NETWORK / N-2 / CWE-295".

- **If mitm shows handshake failures → pinning is PRESENT** — this is a Pass. Verify by loading the SSL bypass and re-checking that traffic now flows.

**Native SSL pinning (BoringSSL/Conscrypt) escalation — mandatory decision tree:**

```
mitm shows TLS errors AND java-layer hooks loaded but still no traffic?
  └─► Confirm: run Python frida script that enumerates loaded classes matching "TrustManager|SSLContext"
      If classes ARE loaded but hooks never call back → native SSL layer (OkHttp3 + BoringSSL).
      Java TrustManager is bypassed before it's ever consulted.

      Escalation (attempt in order):
      1. objection frida gadget: objection patchapk --source <apk>.apk
         → installs libfrida-gadget.so; no frida-server needed; Java hooks fire reliably
      2. Alternatively: use apktool + baksmali to disable pinning checks in smali, re-sign
      3. If neither feasible: document as test-environment limitation; mark auth/crypto blocked
```

Finding classification when native pinning cannot be bypassed:

- The pinning **itself** is a PASS (good security control for production apps).
- Tests that require authenticated traffic (A-2, A-3, N-4, N-5) are marked `Needs Further Investigation`.
- Log the exact error messages from mitm as evidence that pinning is active.

**Summary — pinning decision flow:**

| mitm outcome (no bypass loaded)                | Finding?                  | Action                                                 |
| ---------------------------------------------- | ------------------------- | ------------------------------------------------------ |
| Traffic readable in plain text                 | **YES — Missing Pinning** | Collect traffic sample, screenshot, report High/Medium |
| TLS handshake failures                         | Pass                      | Load SSL bypass, continue with other tests             |
| Hooks load + bypass active but TLS still fails | Native SSL layer          | Escalate to gadget injection; mark auth tests blocked  |

**N-3. Certificate validation** — temporarily install a self-signed cert outside the system trust store and re-test. If the app trusts user-trust-store certs on Android 7+ without a `network_security_config.xml` opt-in, that is a finding for `targetSdk >= 24`.

**N-4. Sensitive data in URLs / headers** — grep transcript for `(?i)token|password|sessionid|jwt|card|cvv|pan|expiry` in URL query strings, `Referer`, and custom headers. For financial apps, also scan for card numbers matching the Luhn pattern (`\b(?:\d[ -]?){13,19}\b`) and CVV/expiry values transmitted in cleartext.

**N-5. Server-side checks** — observed in transcript: tamper a request with mitm `--mode regular` + an interceptor script; replay with modified body/headers and confirm server-side validation. (Optional — flag for the user when out of scope.)

### 7.5 MASVS-PLATFORM — Platform Interaction

**P-1. Exported components abuse** — for each exported activity/service/receiver, attempt invocation:

```bash
adb -s 127.0.0.1:6555 shell am start -n "${PACKAGE}/<exported.Activity>"
adb -s 127.0.0.1:6555 shell am startservice -n "${PACKAGE}/<exported.Service>"
adb -s 127.0.0.1:6555 shell am broadcast -a <action> -n "${PACKAGE}/<exported.Receiver>"
```

Fail if a sensitive activity launches without authentication, or a receiver triggers a privileged action.

**Mandatory evidence for every exported component finding:**

- The **exact verbatim `adb shell am` command** used to trigger the component must appear in the finding's evidence `command` field — not just a description of what happened. Substitute the real class name and action from the manifest, e.g.:
  ```bash
  adb -s 127.0.0.1:6555 shell am broadcast \
    -a owasp.sat.agoat.SHOW_DATA \
    -n owasp.sat.agoat/owasp.sat.agoat.ShowDataReceiver
  ```
- The **raw output / observable result** (Toast text, launched screen, adb output) must be in the `output` field verbatim.
- Three screenshots per the injection screenshot rule: (a) before trigger, (b) command sent, (c) result visible on screen (Toast, new Activity, etc.).

**P-2. Deep-link abuse** — for each declared scheme, run the full test matrix below. Screenshot each result.

```bash
BASE="<scheme>://<host>"   # e.g. ohlq://home or com.ohlq.app.dev://

# Test matrix — run each, screenshot result, note server/client handling
PAYLOADS=(
  "${BASE}/legitimate/path"                              # baseline — confirm it opens
  "${BASE}/?param=<script>alert(1)</script>"             # XSS in query param
  "javascript:alert(document.domain)"                   # JS scheme — should be rejected
  "file:///etc/passwd"                                  # file:// traversal
  "${BASE}/?url=https://evil.example.com"               # open redirect via url param
  "${BASE}/?redirect=//evil.example.com"                # protocol-relative redirect
  "${BASE}/$(python3 -c 'print("A"*4096)')"             # oversized path (buffer overread)
  "${BASE}/?param=%3Cscript%3Ealert%281%29%3C%2Fscript%3E"  # URL-encoded XSS
)

for p in "${PAYLOADS[@]}"; do
  echo "=== Testing: ${p} ==="
  adb -s 127.0.0.1:6555 shell am start -W -a android.intent.action.VIEW -d "${p}" "${PACKAGE}" 2>&1
  sleep 1
  adb -s 127.0.0.1:6555 shell screencap -p /sdcard/deeplink_test.png
  adb -s 127.0.0.1:6555 pull /sdcard/deeplink_test.png "${EVIDENCE_DIR}/screenshots/deeplink_$(date +%s).png"
done
```

Handling classification:

- `javascript:` scheme → if WebView renders it without rejection: **Critical**; if server returns 404 (URL forwarded to server): note server WAF as partial mitigation, still a **Medium** (client should reject before forwarding).
- `file://` scheme → if WebView opens local filesystem: **Critical**.
- XSS in query params forwarded to server → if server WAF blocks: **Medium** (client-side fix still required); if renders: **High**.
- Open redirect → **Medium** for phishing surface.

Note: React Native deep links that route to server-rendered URLs (WebView) are particularly risky because the full URL including scheme substitution reaches the server and may be reflected.

**P-3. Content Provider exposure**

```bash
adb -s 127.0.0.1:6555 shell content query --uri content://<authority>/<path>
adb -s 127.0.0.1:6555 shell content insert ...
```

Fail if a non-permission-protected provider returns user data.

**P-4. WebView misconfiguration** — from jadx + WebView tracer (§10):

- `setJavaScriptEnabled(true)` + `addJavascriptInterface(...)` exposed to untrusted origins → critical
- `setAllowFileAccess(true)` / `setAllowFileAccessFromFileURLs(true)` → critical
- `setMixedContentMode(MIXED_CONTENT_ALWAYS_ALLOW)` → high

**P-5. Custom permission squatting** — review `<permission>` declarations in manifest; confirm protectionLevel.

### 7.6 MASVS-CODE — Code Quality & Mitigations

**Q-1. Debug flag** — `applicationInfo.flags & FLAG_DEBUGGABLE` must be 0 in production:

```bash
adb -s 127.0.0.1:6555 shell dumpsys package "${PACKAGE}" | grep -i flag
```

**Q-2. Verbose error messages** — exercise abuse paths in Phase 4 and inspect responses for stack traces, SQL errors, internal hostnames.

**Q-3. Dynamic code loading** — from jadx (`DexClassLoader`, `PathClassLoader`) and Frida hooking the same — fail if untrusted source loads code at runtime.

**Q-4. Native lib protections** — `objdump -p libfoo.so | grep -i 'BIND_NOW\|stack'`. Lacking `-fstack-protector`, `RELRO`, `PIE` is a defense-in-depth finding.

**Q-5. Outdated dependencies** — extract `META-INF/` and `lib/` versions from APK; cross-check with known-CVE lists. Conservative: only report when the dependency has a documented CVE.

### 7.7 MASVS-RESILIENCE — Anti-Reverse-Engineering

**R-1. Root detection** — already established in Phase 3. **Note**: the absence of root detection is a finding _only_ for high-risk apps (banking, health, payments). For OWASP demo apps it is intentional. Use the user's app context to decide severity.

**R-2. Debugger detection** — `Debug.isDebuggerConnected()` checked? Frida-trace it.

**R-3. Emulator detection** — checks for `Build.FINGERPRINT.contains("generic")`, `goldfish`, etc.

**R-4. Anti-Frida / anti-hooking** — does the app crash or refuse to start when frida-server is running? Test by running with frida-server up vs. down.

**R-5. App integrity (signature check)** — does the app verify its own signature at runtime? Re-sign the APK with a debug key and reinstall; if it still runs unmodified, integrity check is missing.

### 7.8 MASVS-PRIVACY

**Pr-1. Excessive permissions** — manifest review; flag any permission not justified by app functionality.

**Pr-2. Tracking SDKs without consent** — inspect traffic for known tracker hosts before any consent UI is shown.

**Pr-3. PII in analytics** — examine analytics requests in the transcript for emails, phone numbers, full names.

**Pr-4. Analytics/tracking collection before consent** — check manifest for Firebase and analytics metadata flags that auto-enable data collection at install:

```bash
# Flags that indicate pre-consent collection when set to true (or absent, defaulting to true)
grep -E "firebase_analytics_collection_enabled|firebase_automatic_screen_reporting_enabled|
         firebase_crashlytics_collection_enabled|google_analytics_adid_collection_enabled|
         google_analytics_ssaid_collection_enabled|firebase_performance_collection_enabled" \
  "${EVIDENCE_DIR}/static/AndroidManifest.xml"
```

Also check SharedPrefs written at first launch (before any consent UI is shown):

```bash
# After first cold launch, before any user interaction
adb -s 127.0.0.1:6555 shell "run-as ${PACKAGE} ls /data/data/${PACKAGE}/shared_prefs/" | grep -i "firebase\|analytics\|google"
```

Fail if: any of the above flags are `true` (or absent, which defaults to `true`) and the app's own privacy flow requires user consent before analytics activation. Evidence must include the manifest flag values AND the SharedPrefs files written before consent UI appears.

Note: `consent_source: -10` in Firebase Analytics SharedPrefs means analytics are active with no user consent recorded. `consent_settings: G111` means all consent types granted = ad_storage + analytics_storage + ad_user_data + ad_personalization all ON at install.

---

## 8. Evidence Policy

For every finding the report **must** include all of:

1. **Command(s) executed** — verbatim, copy-pasteable.
2. **Raw output** — trimmed only for length (replace removed chunks with `[... trimmed N lines ...]`).
3. **Screenshot(s)** — saved to `${EVIDENCE_DIR}/screenshots/` and referenced by absolute path. For injection / abuse-path findings, three screenshots are required: (a) payload entered, (b) trigger pressed, (c) result/output visible on screen. A screenshot showing only the input field is not sufficient — the output must be captured.
4. **Captured request/response** — for any network-related finding, include the full HTTP request and response (headers + body, verbatim — no redaction).
5. **Frida hook log excerpt** — for any runtime finding caught by a hook.
6. **Source-code excerpt from jadx** — class name + method name + the offending lines, when applicable.

A finding without at least three of the above is downgraded to `Suspected` and is **not** reported.

Confidence levels (use these literally in the report):

- **Confirmed** — reproduced live at least twice, with both static and dynamic evidence.
- **Likely** — clear runtime evidence but only one signal (e.g., hook fired but no source-code corroboration).
- **Suspected** — anomaly observed but not yet reproducible / not fully understood.

Only `Confirmed` and `Likely` get reported. `Suspected` items are listed separately in a "Needs further investigation" appendix so the user can decide whether to re-run.

---

## 9. Report Format

Print this directly to chat at the end of Phase 7. No external file unless requested.

```
# Mobile DAST Report — <Package> — <Date>

## Target
- Package: <pkg>
- Version: <versionName> (<versionCode>)
- Functionality assessed: <Login | All>
- Session evidence: ${DAST_HOME}/evidence/<session>/

## Executive Summary
- Critical: N
- High:     N
- Medium:   N
- Low:      N
- Info:     N
- Tests passed: N / Tests run: N

## Findings

### F-01 — <Short title>
- Severity: Critical | High | Medium | Low | Info
- Confidence: Confirmed | Likely
- MASTG: MASVS-STORAGE / S-1 (Testing Local Storage for Sensitive Data)
- CWE: CWE-312 (Cleartext Storage of Sensitive Information)

**Description**
<2-4 sentences>

**Evidence**
Command:
```

adb -s 127.0.0.1:6555 shell "run-as com.example cat /data/data/com.example/shared_prefs/auth.xml"

```
Output:
```

<map>
  <string name="auth_token">eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...REDACTED...</string>
  <string name="username">test@example.com</string>
</map>
```
Screenshot: /Users/.../evidence/.../screenshots/05_login_success.png
Source (jadx): com.example.auth.AuthManager#saveSession
```java
prefs.edit().putString("auth_token", token).apply(); // line 142
```

**Reproduction**

1. Install and launch the app.
2. Log in with valid credentials.
3. Run the command above.

**Remediation**
Use `EncryptedSharedPreferences` (AndroidX Security Crypto) keyed via the Android KeyStore. Reference: https://developer.android.com/topic/security/data

---

### F-02 — ...

...

## Tests Passed

| Test        | MASTG               | Notes                                                    |
| ----------- | ------------------- | -------------------------------------------------------- |
| TLS pinning | MASVS-NETWORK / N-2 | Pinning verified — mitm handshake failed without bypass. |

| ...

## Needs Further Investigation

- <Suspected items not promoted to findings, with what additional data is needed to resolve them>

## Coverage

- MASVS-STORAGE: 7/7 tests run
- MASVS-CRYPTO: 5/5
- ...

````

Severity rubric:

| Severity | Rule of thumb |
|---|---|
| Critical | Direct compromise (RCE, full account takeover, raw cleartext credentials in storage on a banking/health app). |
| High | Sensitive data exposure, auth bypass on non-trivial flow, exported component leading to sensitive action. |
| Medium | Weak crypto without immediate exploit, missing pinning on non-sensitive app, log leak of moderately sensitive data. |
| Low | Defense-in-depth gap (no root detection on non-sensitive app), minor info leak. |
| Info | Best-practice deviation with no current risk. |

---

## 10. Reusable Frida Hook Library

Save these as standalone scripts in `${DAST_HOME}/scripts/`. Each one follows the same scaffold (process discovery, attach, signal pause). Only the `SCRIPT` body changes.

### 10.1 Universal SSL pinning bypass — `ssl_bypass.py`

Already present in §11 Step 7 — preserved verbatim from the legacy workflow. Add OkHttp v3/v4, Conscrypt, BoringSSL, and `okhttp3.internal.tls` paths if the basic version misses.

**Native SSL layer (BoringSSL/Conscrypt) — when Java hooks are insufficient:**

Java-layer hooks (`SSLContext.init`, `TrustManagerImpl`, `X509TrustManagerExtensions`) work for apps that use Java-managed TLS (HttpsURLConnection, older OkHttp, Volley). They **do not work** for:
- OkHttp3+ on Android 7+ using Conscrypt's native engine
- React Native / Hermes apps (all TLS goes through native OkHttp)
- Apps with `com.android.conscrypt` loaded as a native provider

Diagnostic: hooks load and print `[*] SSL pinning bypass active` but mitm still shows TLS errors → native layer confirmed. Check: `adb shell dumpsys netstats | grep ${PACKAGE}` to confirm network activity is happening despite mitm silence.

Escalation: use `objection patchapk --source ${PACKAGE}.apk` to inject Frida gadget into the APK, which intercepts TLS at a lower level. See §3 Instrumentation Prep for the full decision tree.

### 10.2 Generic root-detection bypass — `root_bypass.py`

Already present in §11 Step 6. Always populate the class/method names from the Phase 2 Recon Report — generic names like `isRooted` are a starting point, not a substitute for static recon.

### 10.3 Crypto inspector — `crypto_inspect.py`

```js
Java.perform(function () {
    var Cipher = Java.use("javax.crypto.Cipher");
    Cipher.getInstance.overload("java.lang.String").implementation = function (t) {
        console.log("[CIPHER] getInstance(" + t + ")");
        return this.getInstance(t);
    };
    var SecretKeySpec = Java.use("javax.crypto.spec.SecretKeySpec");
    SecretKeySpec.$init.overload("[B", "java.lang.String").implementation = function (k, alg) {
        console.log("[KEY] " + alg + " = " + bytes2hex(k));
        return this.$init(k, alg);
    };
    var IvParameterSpec = Java.use("javax.crypto.spec.IvParameterSpec");
    IvParameterSpec.$init.overload("[B").implementation = function (iv) {
        console.log("[IV] " + bytes2hex(iv));
        return this.$init(iv);
    };
    var MessageDigest = Java.use("java.security.MessageDigest");
    MessageDigest.getInstance.overload("java.lang.String").implementation = function (a) {
        console.log("[HASH] " + a);
        return this.getInstance(a);
    };
    function bytes2hex(b) {
        var s = "";
        for (var i = 0; i < b.length; i++) s += ("0" + (b[i] & 0xff).toString(16)).slice(-2);
        return s;
    }
});
````

### 10.4 SharedPreferences writer — `prefs_writer.py`

```js
Java.perform(function () {
  var Editor = Java.use("android.content.SharedPreferences$Editor");
  ["putString", "putInt", "putLong", "putFloat", "putBoolean"].forEach(
    function (m) {
      Editor[m].overloads.forEach(function (ov) {
        ov.implementation = function (k, v) {
          console.log("[PREFS] " + m + "(" + k + ", " + v + ")");
          return ov.call(this, k, v);
        };
      });
    },
  );
});
```

### 10.5 WebView tracer — `webview_trace.py`

```js
Java.perform(function () {
  var WebView = Java.use("android.webkit.WebView");
  WebView.loadUrl.overload("java.lang.String").implementation = function (u) {
    console.log("[WEBVIEW] loadUrl: " + u);
    return this.loadUrl(u);
  };
  WebView.addJavascriptInterface.implementation = function (obj, name) {
    console.log(
      "[WEBVIEW] addJavascriptInterface name=" +
        name +
        " class=" +
        obj.getClass().getName(),
    );
    return this.addJavascriptInterface(obj, name);
  };
  var WebSettings = Java.use("android.webkit.WebSettings");
  WebSettings.setJavaScriptEnabled.implementation = function (b) {
    console.log("[WEBVIEW] setJavaScriptEnabled(" + b + ")");
    return this.setJavaScriptEnabled(b);
  };
});
```

### 10.6 File-IO tracer — `file_trace.py`

Hook `java.io.FileOutputStream.<init>(java.io.File)` and `java.io.FileInputStream.<init>(java.io.File)` — print the path. Useful to map every file the app touches.

### 10.7 Intent dumper — `intent_dump.py`

Hook `android.app.Activity.startActivity` and `Context.sendBroadcast` — print action, component, extras. Catches IPC at runtime even when components are obfuscated.

### 10.8 Clipboard tracer — `clip_trace.py`

Hook `android.content.ClipboardManager.setPrimaryClip` — print the `ClipData` text.

Always launch each hook into its own log file:

```bash
nohup python3.12 ${DAST_HOME}/scripts/<hook>.py \
  > "${EVIDENCE_DIR}/frida/<hook>.log" 2>&1 &
```

---

## 11. Infrastructure Setup (preserved from legacy workflow)

This section is operational plumbing — the same setup the previous Mobile DAST CLAUDE.md described. Steps that already passed in Phase 0 are skipped.

### Step 0 — Preflight Checks

```bash
which mitmdump && mitmdump --version
pgrep -a mitmdump
adb -s 127.0.0.1:6555 shell settings get global http_proxy
adb -s 127.0.0.1:6555 shell ls /system/etc/security/cacerts/c8750f0d.0
adb -s 127.0.0.1:6555 shell "ps -e | grep frida-server"
```

Skip rules:

- Proxy already set to `${MAC_IP}:8080` → skip Step 2.
- Cert hash file present on device → skip Step 3.
- `frida-server` already running → skip Step 4.
- `mitmdump` already running → skip Step 1b.

### Step 1 — Install & start mitmproxy

```bash
which mitmdump || brew install mitmproxy
nohup mitmdump --listen-host 0.0.0.0 --listen-port 8080 -w /tmp/capture.flow > /tmp/mitm.log 2>&1 &
sleep 2 && head -3 /tmp/mitm.log
```

### Step 2 — Configure emulator proxy

```bash
MAC_IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1)
adb -s 127.0.0.1:6555 shell "settings put global http_proxy ${MAC_IP}:8080"
adb -s 127.0.0.1:6555 shell settings get global http_proxy
```

### Step 3 — Install mitmproxy CA as system trust

Genymotion images are root, so we mount-overlay `cacerts/`. The mount is non-persistent — re-run after every emulator reboot.

```bash
CERT_HASH=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
cp ~/.mitmproxy/mitmproxy-ca-cert.pem /tmp/${CERT_HASH}.0
adb -s 127.0.0.1:6555 push /tmp/${CERT_HASH}.0 /data/local/tmp/${CERT_HASH}.0

adb -s 127.0.0.1:6555 shell "su -c '
  mkdir -p /data/local/tmp/cacerts-copy
  cp /system/etc/security/cacerts/* /data/local/tmp/cacerts-copy/
  cp /data/local/tmp/${CERT_HASH}.0 /data/local/tmp/cacerts-copy/
  mount -t tmpfs tmpfs /system/etc/security/cacerts
  cp /data/local/tmp/cacerts-copy/* /system/etc/security/cacerts/
  chown -R root:root /system/etc/security/cacerts
  chmod 644 /system/etc/security/cacerts/*
  chmod 755 /system/etc/security/cacerts
  echo OK
'"
adb -s 127.0.0.1:6555 shell "ls /system/etc/security/cacerts/${CERT_HASH}.0"
```

### Step 4 — Start frida-server on device

```bash
adb -s 127.0.0.1:6555 shell "chmod 755 /data/local/tmp/frida-server"
adb -s 127.0.0.1:6555 shell "nohup /data/local/tmp/frida-server > /data/local/tmp/frida-server.log 2>&1 &"
sleep 2
adb -s 127.0.0.1:6555 shell "ps -e | grep frida-server"
```

### Step 5 — Launch target & verify traffic

```bash
adb -s 127.0.0.1:6555 shell "monkey -p ${PACKAGE} -c android.intent.category.LAUNCHER 1"
sleep 3
tail -20 /tmp/mitm.log
```

### Step 6 — Root detection bypass template

`${DAST_HOME}/scripts/root_bypass.py`:

```python
import frida, signal, sys

PACKAGE      = "PACKAGE_HERE"
PROCESS_NAME = "PROCESS_HERE"

SCRIPT = """
Java.perform(function () {
    // Populate from Phase 2 Recon Report
    var RD = Java.use("CLASS_HERE");
    RD.METHOD_HERE.implementation = function () {
        console.log("[+] METHOD -> false");
        return false;
    };
    console.log("[*] Root detection bypassed");
});
"""

def on_msg(msg, _): print(msg.get("payload", msg)); sys.stdout.flush()
device = frida.get_device("127.0.0.1:6555")
pid    = next(p.pid for p in device.enumerate_processes() if PROCESS_NAME in p.name)
s      = device.attach(pid)
script = s.create_script(SCRIPT); script.on("message", on_msg); script.load()
print(f"[*] Hooked PID {pid}")
signal.pause()
```

### Step 7 — SSL pinning bypass template

`${DAST_HOME}/scripts/ssl_bypass.py`:

```python
import frida, signal, sys
PROCESS_NAME = "PROCESS_HERE"

SCRIPT = """
Java.perform(function () {
    var TM = Java.registerClass({
        name: "com.dast.TrustAll",
        implements: [Java.use("javax.net.ssl.X509TrustManager")],
        methods: {
            checkClientTrusted: function () {},
            checkServerTrusted: function () {},
            getAcceptedIssuers: function () { return []; }
        }
    });
    var SSLContext = Java.use("javax.net.ssl.SSLContext");
    SSLContext.init.overload(
        "[Ljavax.net.ssl.KeyManager;",
        "[Ljavax.net.ssl.TrustManager;",
        "java.security.SecureRandom"
    ).implementation = function (km, tm, sr) {
        console.log("[+] SSLContext.init hooked");
        this.init(km, [TM.$new()], sr);
    };
    try {
        var CertPinner = Java.use("okhttp3.CertificatePinner");
        CertPinner.check.overload("java.lang.String", "java.util.List")
            .implementation = function (host, certs) {
                console.log("[+] OkHttp pinning bypassed: " + host);
            };
    } catch(e) {}
    console.log("[*] SSL pinning bypass active");
});
"""

def on_msg(msg, _): print(msg.get("payload", msg)); sys.stdout.flush()
device = frida.get_device("127.0.0.1:6555")
pid    = next(p.pid for p in device.enumerate_processes() if PROCESS_NAME in p.name)
s      = device.attach(pid)
script = s.create_script(SCRIPT); script.on("message", on_msg); script.load()
print(f"[*] SSL bypass active on PID {pid}")
signal.pause()
```

### Teardown

```bash
adb -s 127.0.0.1:6555 shell "settings put global http_proxy :0"
pkill mitmdump
adb -s 127.0.0.1:6555 shell "pkill frida-server"
pkill -f ${DAST_HOME}/scripts/  # all hooks
```

---

## 12. JADX Static Analysis — Detail

The legacy workflow described JADX as a "Pre-DAST recon" optional step. In this AI-guided workflow it is **mandatory** for Phase 2 and feeds every other phase.

### Setup

```bash
# 1. Open the pulled APK in JADX-GUI
open -a jadx-gui ${DAST_HOME}/apks/${PACKAGE}.apk

# 2. The jadx-mcp-server bridge is already configured at port 8085.
#    No additional action; just call the mcp__jadx-mcp-server__* tools.
```

### Tool routing inside jadx-mcp-server

| Need                                                  | Tool                              |
| ----------------------------------------------------- | --------------------------------- |
| Manifest contents                                     | `get_android_manifest`            |
| Specific manifest component                           | `get_manifest_component`          |
| All classes (paginated)                               | `get_all_classes`                 |
| Decompile a class                                     | `get_class_source`                |
| Smali (obfuscation cases)                             | `get_smali_of_class`              |
| Search by keyword                                     | `search_classes_by_keyword`       |
| Search by method name                                 | `search_method_by_name`           |
| All extracted strings                                 | `get_strings`                     |
| Specific resource (e.g., network_security_config.xml) | `get_resource_file`               |
| Cross-references to a method/class/field              | `get_xrefs_to_method/class/field` |

### Pulling the APK

```bash
APK_PATH=$(adb -s 127.0.0.1:6555 shell pm path "${PACKAGE}" | head -1 | sed 's/^package://')
adb -s 127.0.0.1:6555 pull "${APK_PATH}" "${DAST_HOME}/apks/${PACKAGE}.apk"
```

If the app uses split APKs (`base.apk` + `split_*.apk`), pull all of them — JADX needs `base.apk` minimum, but missing splits cause method resolution gaps.

---

## 13. Tested App Inventory (carry-over, update as new apps run)

| App                  | Package                        | Root Check                                                      | SSL Pinning                                                                                                                                            | Notes                                                                                                                                                                                                                                                                              |
| -------------------- | ------------------------------ | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OWASP AndroGoat      | `owasp.sat.agoat`              | `owasp.sat.agoat.RootDetectionActivity.{isRooted,isRooted1}`    | No                                                                                                                                                     | Demo app — most tests will be intentional findings                                                                                                                                                                                                                                 |
| InsecureBankv2       | `com.android.insecurebankv2`   | Unknown                                                         | Unknown                                                                                                                                                | Demo app                                                                                                                                                                                                                                                                           |
| DamnVulnerableBank   | `com.app.damnvulnerablebank`   | Unknown                                                         | Unknown                                                                                                                                                | Demo app                                                                                                                                                                                                                                                                           |
| Telus Health Chatbot | `com.telus.health.chatbot.sdk` | Unknown                                                         | Likely yes                                                                                                                                             | Production — pinning bypass likely needed; treat severities seriously                                                                                                                                                                                                              |
| Telus SmartHome      | `com.telus.smarthome.vmo`      | Unknown                                                         | Likely yes                                                                                                                                             | Production                                                                                                                                                                                                                                                                         |
| OHLQ (Dev)           | `com.ohlq.app.dev`             | **None** — `m6.E` is Firebase OsData telemetry, not enforcement | **Yes** — native BoringSSL/Conscrypt layer; Java hooks load but never fire; spawn-mode bypass crashes app ~12s; recommend APK repack with Frida gadget | Dev build (Expo SDK 52 / RN / Hermes). Hardcoded Braze+Firebase+Maps API keys. `usesCleartextTraffic=true`. Missing `FLAG_SECURE`. Analytics enabled pre-consent. reCAPTCHA Enterprise blocks emulator login. Auth/crypto tests blocked. Session: `evidence/2026-04-28_1121_OHLQ/` |

When testing an unfamiliar app, after the run append a new row with:

- root-detection class+method (if found in Phase 2)
- whether SSL pinning was active
- any quirks (custom anti-Frida, native crypto, etc.)

---

## 14. Common Pitfalls (and how to avoid them)

- **App crashes on launch with frida-server up** — anti-Frida. Try `frida-gadget` injection via APK repack, or spawn-attach (`device.spawn` + `device.resume`) instead of attach-after-launch.
- **mitm shows zero traffic for a working app** — either pinning is on (load SSL bypass) or app uses raw sockets / gRPC / QUIC (not HTTP-proxy-able). Check the network logs in `dumpsys netstats`.
- **`run-as ${PACKAGE}` fails** — app is not debuggable. Genymotion images are usually root, so fall back to `su -c` to read `/data/data/${PACKAGE}/`.
- **`mobile_list_elements_on_screen` returns empty** — a Compose / Flutter / Unity view that doesn't expose accessibility nodes. Fall back to `mobile_take_screenshot` + reasoning over the image, then `mobile_click_on_screen_at_coordinates` with image-derived coordinates.
- **Frida hook didn't fire** — class name was obfuscated. Re-search jadx for the _content_ (the offending string constant) rather than the _name_. Use `Java.enumerateLoadedClasses` at runtime to see what's actually loaded.
- **Genymotion reboot** — system-CA mount is gone. Re-run §11 Step 3.
- **OWASP demo apps** — almost everything will be intentionally vulnerable. Don't pad the report; pick the most pedagogically useful 5–10 findings and explain them well.
- **Java SSL hooks load but TLS still doesn't flow (BoringSSL/Conscrypt)** — React Native, modern OkHttp3, and apps using Conscrypt as the security provider perform TLS handshakes at the native layer. `SSLContext.init`, `TrustManagerImpl`, and `X509TrustManagerExtensions` hooks will print `[*] active` but are never consulted during actual connections. Diagnostic: run `Java.enumerateLoadedClasses` and check for `com.android.org.conscrypt` or `com.google.android.gms.org.conscrypt` — if present, you have native SSL. Fix: APK gadget injection (see §3, §10.1).
- **Spawn mode with SSL hooks → app crash ~12s** — the hook interaction during native Conscrypt/BoringSSL initialisation destabilises the process. Do NOT keep retrying spawn mode. Switch to attach-only (accepts the limitation that OkHttp is already initialized) or gadget injection.
- **reCAPTCHA Enterprise blocks login on emulator** — reCAPTCHA Enterprise requires real Google TLS to bootstrap its attestation token. When mitm proxy intercepts Google endpoints, reCAPTCHA SDK never initialises and the login button's `onPress` callback never fires. Mitigations: (a) temporarily disable proxy for `*.google.com` / `*.gstatic.com` in mitm's `ignore_hosts`; (b) bypass the reCAPTCHA SDK via Frida (hook `RecaptchaClient.execute` → return a fake token); (c) patch the minimum threshold in the Redux/manifest config to 0.0.
- **`isRooted` / `m6.E` false positive** — searching for `isRooted` in jadx will find Firebase's `OsData` telemetry model (class `m6.E` or similar obfuscated names) which stores `isRooted` as a boolean field. This is NOT app-level root enforcement — it just records device state for analytics. Always call `get_class_source` on any candidate class and confirm it actually gates the application flow (throws exception, shows dialog, kills process) before reporting it as root detection.
- **mcp-cli-exec shell variable persistence** — each `mcp-cli-exec` tool call spawns a fresh shell. Variables set in one call (e.g., `EDIR="/path/..."`) are NOT available in the next call. Never split variable assignment and use across separate tool calls. Fix: always use **absolute paths** inline, or `cd` into the target directory within the **same** command string, e.g.: `cd ${DAST_HOME}/evidence/session/ && find . -type f | sort > INDEX.txt`.
- **`Write` tool cannot write to `$HOME/...`** — the `Write`/`Edit` tools operate in the sandboxed session filesystem. To write evidence files to the user's /mobile-dast tree, use `mcp-cli-exec` with a heredoc: `cat > "$HOME/.../file.xml" << 'EOF' ... EOF`. This is the correct and only pattern for writing static artifacts to the evidence directory.
- **ADB backup dialog timing** — `adb backup` is a blocking foreground command. If Claude sends it as a background process (`&`) and then tries to tap the dialog, the backup PID may differ from an earlier stale dialog. Pattern: run `adb backup -f /path/out.ab ${PACKAGE} &`, capture the PID immediately, wait 2s, then tap the dialog; then `wait` on the PID to confirm it completed.

---

## 15. Quick-Start — When The User Says "Run a Mobile DAST"

The full kickoff conversation should look like this:

```
USER: Package: com.andro.goat
      Functionality: Login

CLAUDE: [Phase 0] Preflight passing — mitm up, proxy set, CA installed, frida-server running.
        Loaded credentials from .env (keys: USER_NAME EMAIL PASSWORD).
        [Phase 1] Resolved package owasp.sat.agoat (matched on substring "andro.goat" via pm list).
        Pulled APK to apks/owasp.sat.agoat.apk.
        [Phase 2] Static recon report: ...
        [Phase 3] Loading root_bypass + crypto_inspect Frida hooks.
        [Phase 4] Driving login flow via mobile-mcp ... screenshots saved.
        [Phase 5] Running MASTG loops ... 18 tests applicable, 18 executed.
        [Phase 6] Evidence consolidated to evidence/2026-04-28_1430_owasp_sat_agoat/.
        [Phase 7] Report:

        # Mobile DAST Report — owasp.sat.agoat — 2026-04-28
        ...
```

Claude does not narrate every shell command in chat — it summarizes per phase and surfaces command output only inside findings. The full command transcript lives in the evidence directory.

---

## 16. React Native / Expo / Hermes — Architecture-Specific Guidance

React Native apps have fundamentally different internals from native Java apps. Adjust the entire workflow when Phase 2 detects RN:

### 16.1 Detection Signals

```bash
# APK contains JS bundle (plain-text RN or Expo managed workflow)
unzip -p ${DAST_HOME}/apks/${PACKAGE}.apk assets/index.android.bundle | head -1

# APK contains Hermes bytecode (Expo SDK 48+ default; RN 0.70+)
unzip -p ${DAST_HOME}/apks/${PACKAGE}.apk assets/index.android.bundle.hbc | xxd | head -1
# Hermes magic bytes: c6 1f bc 03 (little-endian) or "HBC" header variant

# Java package list shows React Native
# jadx: search_classes_by_keyword("com.facebook.react") or ("expo")
```

### 16.2 Storage — Primary Targets

| Storage layer                  | Location                                                                                            | Access                        |
| ------------------------------ | --------------------------------------------------------------------------------------------------- | ----------------------------- |
| AsyncStorage (RN built-in)     | `/data/data/${PKG}/databases/RKStorage.db`                                                          | `run-as` or `su -c cat`       |
| Redux Persist (`persist:root`) | Row in `RKStorage.db` → `catalystLocalStorage` table                                                | `sqlite3 .dump`               |
| expo-secure-store              | Android Keystore-backed; only accessible via Frida hook on `SecureStoreModule.getValueWithKeyAsync` | Frida                         |
| react-native-keychain          | Android Keystore or SharedPrefs depending on config                                                 | `shared_prefs/` + Frida       |
| MMKV (fast storage lib)        | `/data/data/${PKG}/files/mmkv/` as binary `.crc` files                                              | pull + `mmkv_cli` or hex dump |

**Redux Persist audit procedure:**

```bash
# Pull and pretty-print the entire persist:root JSON
sqlite3 "${EVIDENCE_DIR}/dynamic/RKStorage.db" \
  "SELECT value FROM catalystLocalStorage WHERE key='persist:root';" \
  > /tmp/persist_root.json

python3 -c "
import json, sys
outer = json.load(sys.stdin)
for k, v in outer.items():
    try: inner = json.loads(v); print(f'=== {k} ==='); print(json.dumps(inner, indent=2)[:500])
    except: print(f'=== {k} (raw) ==='); print(str(v)[:200])
" < /tmp/persist_root.json > "${EVIDENCE_DIR}/dynamic/persist_root_pretty.txt"
```

Look for: SDK API keys embedded in config slices, auth tokens written post-login, feature flags, backend URLs.

### 16.3 Frida — What Works vs. What Doesn't

| Hook target                                | Works?          | Notes                                                                |
| ------------------------------------------ | --------------- | -------------------------------------------------------------------- |
| Java SharedPreferences                     | ✅              | SDK native modules (Braze, Firebase) use Java prefs                  |
| Java Cipher / SecretKeySpec                | ✅              | If any Java crypto exists in native modules                          |
| JS-layer business logic                    | ❌              | Hermes bytecode — no Java classes for app logic                      |
| OkHttp Java-layer SSL                      | ❌ (native SSL) | See §10.1 / §3                                                       |
| `com.facebook.react.bridge` Native Modules | ✅              | Hook `NativeModuleBase` subclasses for storage, auth, crypto bridges |

To find what native modules exist:

```bash
# jadx
# search_classes_by_keyword("NativeModule") or search_method_by_name("getName")
# Each NativeModule's getName() return value = the JS-callable module name
```

### 16.4 Network — React Native Specifics

- All HTTP(S) goes through OkHttp3 native (not HttpsURLConnection). Java-layer SSL hooks insufficient — see §3.
- The JS bundle may contain hardcoded API base URLs, staging/dev endpoints, and even SDK keys. Scan the bundle:
  ```bash
  unzip -p ${DAST_HOME}/apks/${PACKAGE}.apk assets/index.android.bundle \
    | strings | grep -iE "(https?://|api[_-]?key|secret|token|braze|firebase|amplitude)" \
    | head -50 > "${EVIDENCE_DIR}/static/bundle_strings.txt"
  ```
  For Hermes `.hbc`: use `hbctool` or `hermes-dec` to disassemble before grepping.

### 16.5 reCAPTCHA Enterprise on Emulator

reCAPTCHA Enterprise (used in production RN apps) requires:

1. Real device attestation (Play Integrity / SafetyNet)
2. Google TLS reachable (breaks under mitm proxy)

When both conditions fail simultaneously, the login button's JS `onPress` handler exits silently. No error is shown. The app appears frozen.

Mitigations (try in order):

1. **Proxy exclusion**: add `*.google.com,*.gstatic.com,*.googleapis.com` to mitm `--ignore-hosts` — this lets reCAPTCHA bootstrap while still capturing app traffic.
2. **Frida hook**: intercept the RN Native Module bridging the reCAPTCHA call and return a static fake token string.
3. **Manifest patch**: lower `RECAPTCHA_SITE_KEY` or the score threshold to 0.0 via `apktool` smali edit if keys are in resources.
4. **Accept the blocker**: if none work, document login as inaccessible in the emulator environment and focus on static, storage, and pre-auth tests.

---

## 17. Out Of Scope / What Claude Will Not Do

- Source modifications to the target app (no APK repacking unless the user explicitly asks).
- Server-side fuzzing beyond what is needed to validate a client-side finding.
- Bypassing controls on apps the user does not own / is not authorized to test. If the brief is for an app whose authorization is unclear, Claude asks once before running.
- Anything that violates the user's organization policies (e.g., uploading APKs to public scanners). All work stays local.
