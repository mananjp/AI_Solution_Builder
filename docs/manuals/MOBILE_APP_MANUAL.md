# AI Solution Builder — Mobile & Android Manual
# CHAOS2COMMIT Hackathon 2026 — Futurrizon Technologies Pvt Ltd

This document provides setup, compilation, and testing instructions for the mobile experience of **AI Solution Builder**, including the Progressive Web App (PWA) and the native **Android Capacitor Application**.

---

## 1. Mobile Architecture Overview

AI Solution Builder adopts a unified responsive frontend architecture powered by **Next.js 16** and **Capacitor 8.5**:
1. **Responsive Web & PWA:**
   - Adapts dynamically to all viewport sizes (smartphones, tablets, foldables).
   - Features a bottom navigation bar (`MobileBottomNav.tsx`) for primary actions (Dashboard, Chat, Solutions, Settings).
   - Touch-optimized gesture controls, drawers, and modal sheets.
   - PWA Service Worker caching for fast load times and offline asset availability.
2. **Capacitor Android Shell:**
   - Native Android wrapper located at `frontend/android/`.
   - Direct integration with Android hardware APIs (haptic feedback, status bar theming, secure storage).
   - Compiled to standalone APK for distribution on Android devices or Google Play Store.

---

## 2. Testing the Mobile Responsive Web Experience

To test the mobile interface in your desktop browser:
1. Start the frontend:
   ```bash
   cd frontend
   npm run dev
   ```
2. Open `http://localhost:3000` in Google Chrome or Firefox.
3. Press `F12` to open Developer Tools, then click the **Toggle Device Toolbar** icon (`Ctrl+Shift+M` or `Cmd+Shift+M`).
4. Select a mobile profile such as **Pixel 7**, **iPhone 14 Pro**, or **Samsung Galaxy S22**.
5. Observe the UI automatically transforming:
   - Desktop sidebar collapses into a hidden drawer.
   - Bottom navigation bar appears fixed at the bottom with quick access buttons.
   - Dashboard cards rearrange into single-column responsive grids.

---

## 3. Building and Running the Android App

### Prerequisites
- Java Development Kit (JDK 17 or JDK 21)
- Android Studio Ladybug (or newer) with Android SDK 34/35
- Node.js 20+

### Step-by-Step Build Instructions

1. **Export the Next.js Frontend:**
   ```bash
   cd frontend
   npm run build
   ```

2. **Sync Frontend Assets to the Android Native Project:**
   ```bash
   npx cap sync android
   ```
   This command copies compiled static assets and plugins into `frontend/android/app/src/main/assets/public`.

3. **Open Project in Android Studio:**
   ```bash
   npx cap open android
   ```
   Or launch Android Studio manually and select the folder:
   `D:\git\AI_Solution_Builder\frontend\android`

4. **Run on an Android Device or Emulator:**
   - In Android Studio, select your target device or Android Virtual Device (AVD).
   - Click the green **Run** button (`Shift + F10`).
   - The app will compile and launch `com.futurrizon.aisolutionbuilder`.

5. **Generate a Standalone Release APK:**
   - In Android Studio: **Build** → **Build Bundle(s) / APK(s)** → **Build APK(s)**.
   - Or via command line in PowerShell:
     ```bash
     cd frontend/android
     ./gradlew assembleRelease
     ```
   - The generated release APK will be located at:
     `frontend/android/app/build/outputs/apk/release/app-release-unsigned.apk`

---

## 4. Key Android Configuration Files

| File | Purpose |
|------|---------|
| `frontend/capacitor.config.ts` | App ID (`com.futurrizon.aisolutionbuilder`), app name, web dir |
| `frontend/android/app/src/main/AndroidManifest.xml` | Android permissions (Internet, Network State) |
| `frontend/android/app/build.gradle` | Android SDK versions (`minSdkVersion 22`, `targetSdkVersion 34`) |
| `frontend/src/components/MobileNav.tsx` | Mobile bottom navigation component |
